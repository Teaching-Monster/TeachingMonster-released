#!/usr/bin/env python3
"""
Slides PPT Module

Main entry point for the slide generation system.
Uses Gemini API for intelligent layout generation and programmatic rendering.
"""

import asyncio
import os
import shutil
from typing import Any, Dict, List, Optional

from src.config_schema import PPTConfig
from src.gemini_client import GeminiClient
from .orchestrator import SlideOrchestrator


class SlidesModule_PPT:
    """
    Slides generation module using Gemini-powered Designer and programmatic Render.

    Input:
        list[dict[str, Any]]
        Each dict represents one slide with:
        - id: Unique slide identifier
        - title: Slide title (optional)
        - content: Content description or body text
        - layout_hint: Suggested layout type (optional)
        - Any additional metadata for the designer

    Output:
        str: Path to folder containing generated slide images
             (e.g., slide_1.jpg, slide_2.jpg, ...)
    """

    def __init__(
        self,
        llm_client: GeminiClient,
        config: PPTConfig,
        output_root: str = "./slides_output",
        max_concurrent_slides: int = 3,
    ):
        """
        Initialize the Slides PPT Module.

        Args:
            llm_client: GeminiClient instance for LLM-powered design
            output_root: Root directory for output files
            max_concurrent_slides: Max number of slides processed in parallel
            max_retries: Total attempts per slide before permanent failure
            retry_base_delay: Base delay in seconds for exponential backoff
            max_review_rounds: Maximum reviewer refinement rounds per slide (0 = disabled)
            review_threshold: Minimum score to approve a slide without refinement
        """
        self.llm = llm_client
        self.config = config
        self.output_root = output_root
        self.max_concurrent_slides = max_concurrent_slides
        self.max_retries = self.config.max_retries
        self.retry_base_delay = self.config.retry_base_delay
        self.max_review_rounds = self.config.max_review_rounds
        self.review_threshold = self.config.review_threshold
        self.is_loaded = False
        self._orchestrator: Optional[SlideOrchestrator] = None

    def load(self):
        """
        Load models / heavy resources.
        """
        self.llm.load()
        self.is_loaded = True

    def run(self, slides: List[Dict[str, Any]]) -> str:
        """
        Generate slide images from abstract slide descriptions.

        Args:
            slides: List of slide dictionaries with content descriptions

        Returns:
            folder_path (str): Path to folder containing generated images

        Note:
            This method uses asyncio.run() internally to drive the async pipeline.
            It cannot be called from within an already-running event loop (e.g. inside
            an async function). In that case, await the orchestrator.run() directly.
        """
        assert self.is_loaded, "Call load() before run()"

        # Input validation
        if not isinstance(slides, list):
            raise TypeError(f"Expected slides to be a list, got {type(slides)}")

        if len(slides) == 0:
            raise ValueError("slides list cannot be empty")

        # Validate output_root
        if not self.output_root:
            raise ValueError("output_root cannot be None or empty")

        # Create output directory
        try:
            os.makedirs(self.output_root, exist_ok=True)
        except OSError as e:
            msg = f"Failed to create output directory '{self.output_root}': {e}"
            raise RuntimeError(msg) from e

        # Clean up old slide files
        self._cleanup_old_files()

        # Ensure slides have IDs
        for idx, slide in enumerate(slides, start=1):
            if "id" not in slide:
                slide["id"] = f"slide_{idx}"

        # Initialize orchestrator
        self._orchestrator = SlideOrchestrator(
            llm_client=self.llm,
            output_dir=self.output_root,
            max_retries=self.max_retries,
            retry_base_delay=self.retry_base_delay,
            max_review_rounds=self.max_review_rounds,
            review_threshold=self.review_threshold,
        )

        # Run the async pipeline from this sync entry point
        results = asyncio.run(
            self._orchestrator.run(slides, max_concurrent=self.max_concurrent_slides)
        )

        # Rename output images to sequential numbering (1.jpg, 2.jpg, etc.)
        self._rename_outputs(results)

        # Create merged presentation
        self._orchestrator.merge_final_presentation("presentation.pptx")

        return self.output_root

    def _cleanup_old_files(self):
        """Clean up old slide files before generating new ones."""
        if os.path.exists(self.output_root):
            for filename in os.listdir(self.output_root):
                # Remove image files
                if filename.endswith((".jpg", ".png", ".pptx")):
                    old_file_path = os.path.join(self.output_root, filename)
                    try:
                        os.remove(old_file_path)
                    except OSError:
                        pass

    def _rename_outputs(self, results: List[Dict[str, Any]]):
        """
        Rename output images to sequential numbering.

        Args:
            results: List of processing results from orchestrator
        """
        for idx, result in enumerate(results, start=1):
            if result.get("success") and result.get("image_path"):
                old_path = result["image_path"]
                new_path = os.path.join(self.output_root, f"{idx}.jpg")

                if os.path.exists(old_path) and old_path != new_path:
                    try:
                        shutil.move(old_path, new_path)
                    except OSError:
                        pass

    def get_results(self) -> List[Dict[str, Any]]:
        """
        Get the detailed results from the last run.

        Returns:
            List of result dictionaries for each slide
        """
        if self._orchestrator:
            return self._orchestrator.results
        return []

    def save_layouts(self, filename: str = "layouts.json") -> Optional[str]:
        """
        Save the generated layouts to a JSON file.

        Args:
            filename: Output filename

        Returns:
            Path to saved file or None
        """
        if self._orchestrator:
            return self._orchestrator.save_refined_content(filename)
        return None
