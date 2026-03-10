#!/usr/bin/env python3
"""
Orchestrator Module

Central controller that coordinates the slide generation workflow.
Manages the Designer → Render → Reviewer pipeline.
"""

import asyncio
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pptx import Presentation
from pptx.util import Inches

from src.gemini_client import GeminiClient
from .designer_agent import DesignerAgent
from .render_agent import RenderAgent
from .reviewer_agent import ReviewerAgent
from . import slide_generator


class SlideOrchestrator:
    """
    Central orchestrator for the slide generation system.

    Coordinates:
    - Designer Agent (Gemini): Abstract → Layout JSON
    - Render Agent: Layout JSON → PPTX + Image
    - Reviewer Agent (vision LLM): Image → score + optional refined layout
    """

    def __init__(
        self,
        llm_client: GeminiClient,
        output_dir: str,
        max_retries: int = 5,
        retry_base_delay: float = 2.0,
        max_review_rounds: int = 5,
        review_threshold: float = 9.0,
    ):
        """
        Initialize the Orchestrator.

        Args:
            llm_client: GeminiClient instance for LLM inference
            output_dir: Directory to save generated files
            max_retries: Total attempts per slide before permanent failure
            retry_base_delay: Base delay in seconds for exponential backoff
            max_review_rounds: Maximum reviewer refinement rounds per slide (0 = disabled)
            review_threshold: Minimum score to approve a slide without refinement
        """
        self.llm_client = llm_client
        self.output_dir = output_dir
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.max_review_rounds = max_review_rounds
        self.review_threshold = review_threshold

        # Agent instances
        self._designer: Optional[DesignerAgent] = None
        self._render: Optional[RenderAgent] = None
        self._reviewer: Optional[ReviewerAgent] = None

        # Results storage
        self.results: List[Dict[str, Any]] = []

    def _ensure_agents(self) -> None:
        """Ensure all agents are initialized."""
        if self._designer is None:
            self._designer = DesignerAgent(self.llm_client)

        if self._render is None:
            # Pass Gemini API key to render agent for image generation
            api_key = getattr(self.llm_client.config, 'api_key', None)
            self._render = RenderAgent(self.output_dir, gemini_api_key=api_key)

        if self._reviewer is None:
            self._reviewer = ReviewerAgent(self.llm_client, score_threshold=self.review_threshold)

    @property
    def designer(self) -> DesignerAgent:
        """Get the Designer Agent instance."""
        self._ensure_agents()
        return self._designer

    @property
    def render(self) -> RenderAgent:
        """Get the Render Agent instance."""
        self._ensure_agents()
        return self._render

    @property
    def reviewer(self) -> ReviewerAgent:
        """Get the Reviewer Agent instance."""
        self._ensure_agents()
        return self._reviewer

    async def _process_slide_once(self, slide_prompt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single slide through the full pipeline (one attempt).

        Args:
            slide_prompt: Abstract slide description

        Returns:
            Result dict with success status and final content
        """
        slide_id = slide_prompt.get("id", "unknown")
        print(f"\n{'='*50}")
        print(f"Processing Slide: {slide_id}")
        print(f"{'='*50}")

        # Step 1: Designer generates layout
        print("[1/2] Designer: Generating layout...")
        layout_json = await self.designer.design_layout(slide_prompt)

        if not layout_json:
            print(f"Designer failed for {slide_id}")
            return {
                "id": slide_id,
                "success": False,
                "error": "Failed to generate layout",
                "final_layout": None,
                "pptx_path": None
            }

        # Save designer output to file (fast sync I/O)
        layout_output_path = os.path.join(self.output_dir, f"{slide_id}_layout.json")
        with open(layout_output_path, 'w', encoding='utf-8') as f:
            json.dump(layout_json, f, indent=2, ensure_ascii=False)
        print(f"    Layout saved to: {layout_output_path}")

        # Step 2: Render generates PPTX and image
        print("[2/2] Render: Generating PPTX and image...")
        render_result = await self.render.render(layout_json)

        if not render_result.get("success"):
            print(f"Render failed for {slide_id}: {render_result.get('error')}")
            return {
                "id": slide_id,
                "success": False,
                "error": render_result.get("error", "Render failed"),
                "final_layout": layout_json,
                "pptx_path": render_result.get("pptx_path")
            }

        # Step 3: Reviewer quality loop
        if self.max_review_rounds > 0:
            image_path = render_result.get("image_path")

            for round_num in range(1, self.max_review_rounds + 1):
                if not image_path or not os.path.exists(image_path):
                    print(f"    [reviewer] No image available, skipping review")
                    break

                print(f"[reviewer] Round {round_num}/{self.max_review_rounds} for {slide_id}...")
                review = await self.reviewer.review(image_path, layout_json, slide_prompt)
                score = review.get("score", 10)
                print(f"    Score: {score:.1f}/10 — {review.get('reason', '')}")

                if review.get("approved"):
                    print(f"    ✓ Approved (score {score:.1f} ≥ {self.review_threshold})")
                    break

                refined = review.get("refined_layout")
                if not refined:
                    print(f"    No refined layout returned, keeping current version")
                    break

                # Preserve slide id — reviewer LLM may omit it
                refined["id"] = slide_id
                # Normalise content shape — LLM may return a bare list of elements
                if isinstance(refined.get("content"), list):
                    refined["content"] = {"elements": refined["content"]}

                v = round_num + 1
                refined_path = os.path.join(self.output_dir, f"{slide_id}_layout_v{v}.json")
                with open(refined_path, 'w', encoding='utf-8') as f:
                    json.dump(refined, f, indent=2, ensure_ascii=False)
                print(f"    Refined layout → {refined_path}")

                layout_json = refined
                render_result = await self.render.render(layout_json)
                if not render_result.get("success"):
                    print(f"    Re-render failed: {render_result.get('error')}")
                    break
                image_path = render_result.get("image_path")

        print(f"✓ Slide {slide_id} completed successfully!")

        return {
            "id": slide_id,
            "success": True,
            "final_layout": layout_json,
            "pptx_path": render_result.get("pptx_path"),
            "image_path": render_result.get("image_path")
        }

    async def process_slide(self, slide_prompt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single slide with exponential-backoff retry.

        Calls _process_slide_once() up to self.max_retries times.  A failure is
        either an exception or a result dict with success=False.

        Args:
            slide_prompt: Abstract slide description

        Returns:
            Result dict from the first successful attempt, or the last failure.
        """
        slide_id = slide_prompt.get("id", "unknown")
        last_result = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._process_slide_once(slide_prompt)
                if result.get("success"):
                    return result
                last_result = result
                err = result.get("error", "unknown error")
            except Exception as e:
                last_result = {
                    "id": slide_id, "success": False,
                    "error": str(e), "final_layout": None, "pptx_path": None
                }
                err = str(e)

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** (attempt - 1))
                print(f"[retry] Slide {slide_id} failed (attempt {attempt}/{self.max_retries}): {err}")
                print(f"[retry] Waiting {delay:.1f}s before next attempt...")
                await asyncio.sleep(delay)
            else:
                print(f"[retry] Slide {slide_id} permanently failed after {self.max_retries} attempts.")

        return last_result

    async def run(
        self,
        slides_data: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process all slides concurrently and return results in input order.

        Args:
            slides_data: List of abstract slide descriptions
            max_concurrent: Maximum number of slides processed simultaneously

        Returns:
            List of result dicts for each slide (same order as input)
        """
        # Ensure every slide has a unique id so output files never collide
        for idx, slide in enumerate(slides_data, start=1):
            if not slide.get("id"):
                slide["id"] = f"slide_{idx}"

        print(f"\n{'='*60}")
        print(f"Starting Slide Pipeline - {len(slides_data)} slides (max {max_concurrent} concurrent)")
        print(f"{'='*60}")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_process(slide: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.process_slide(slide)

        tasks = [bounded_process(slide) for slide in slides_data]
        self.results = list(await asyncio.gather(*tasks))

        # Summary
        success_count = sum(1 for r in self.results if r.get("success"))
        print(f"\n{'='*60}")
        print(f"Pipeline Complete: {success_count}/{len(self.results)} slides succeeded")
        print(f"{'='*60}")

        return self.results

    def merge_final_presentation(
        self,
        filename: str = "final_presentation.pptx"
    ) -> Optional[str]:
        """
        Merge all successful slides into a single presentation.

        Args:
            filename: Output filename

        Returns:
            Path to merged presentation or None if failed
        """
        successful_layouts = [
            r["final_layout"]
            for r in self.results
            if r.get("success") and r.get("final_layout")
        ]

        if not successful_layouts:
            print("No successful slides to merge.")
            return None

        print(f"\nMerging {len(successful_layouts)} slides into {filename}...")

        # Create new presentation
        merged_prs = Presentation()
        merged_prs.slide_width = Inches(13.333)
        merged_prs.slide_height = Inches(7.5)

        for slide_data in successful_layouts:
            layout = slide_data.get("layout", "CONTENT").upper()
            content = slide_data.get("content", {})
            # Normalise: LLM sometimes returns content as a bare list of elements
            if isinstance(content, list):
                content = {"elements": content}
            style = slide_data.get("style", {})

            if "elements" in content and isinstance(content["elements"], list):
                slide_generator.create_custom_slide(merged_prs, content, style)
            elif layout == "TITLE":
                slide_generator.create_title_slide(merged_prs, content, style)
            elif layout == "SECTION":
                slide_generator.create_section_slide(merged_prs, content, style)
            elif layout == "CUSTOM":
                slide_generator.create_custom_slide(merged_prs, content, style)
            elif layout == "TWO_CONTENT":
                slide_generator.create_two_content_slide(merged_prs, content, style)
            elif layout == "COMPARISON":
                slide_generator.create_comparison_slide(merged_prs, content, style)
            else:
                slide_generator.create_content_slide(merged_prs, content, style)

        final_path = os.path.join(self.output_dir, filename)
        merged_prs.save(final_path)
        print(f"✓ Merged presentation saved to: {final_path}")

        return final_path

    def save_refined_content(
        self,
        filename: str = "refined_content.json"
    ) -> str:
        """
        Save all final layouts to a JSON file.

        Args:
            filename: Output filename

        Returns:
            Path to saved JSON file
        """
        refined_content = [
            r["final_layout"]
            for r in self.results
            if r.get("final_layout")
        ]

        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(refined_content, f, indent=2, ensure_ascii=False)

        print(f"Refined content saved to: {output_path}")
        return output_path
