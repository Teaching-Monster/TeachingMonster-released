#!/usr/bin/env python3
"""
Render Agent Module

Responsible for converting Layout JSON into PPTX files and rendering them as images.
Includes image generation via Gemini Imagen for slides with image prompts.
"""

import asyncio
import os
import json
import hashlib
from typing import Dict, Any, Optional

from . import slide_generator

# Optional: Import Gemini for image generation
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_IMAGEN = True
except ImportError:
    HAS_GEMINI_IMAGEN = False


_IMAGEN_RATIOS = {
    "1:1": 1.0,
    "9:16": 9 / 16,
    "16:9": 16 / 9,
    "4:3": 4 / 3,
    "3:4": 3 / 4,
}


def _pick_aspect_ratio(w: float, h: float) -> str:
    ratio = w / h
    return min(_IMAGEN_RATIOS, key=lambda k: abs(_IMAGEN_RATIOS[k] - ratio))


class RenderAgent:
    """
    Render Agent that converts Layout JSON to PPTX and images.

    Supports:
    - PPTX generation from layout JSON
    - Image generation via Gemini Imagen API
    - PPTX to image conversion
    """

    def __init__(self, output_dir: str, gemini_api_key: Optional[str] = None):
        """
        Initialize the Render Agent.

        Args:
            output_dir: Directory to save generated files
            gemini_api_key: Optional Gemini API key for image generation
        """
        self.name = "render"
        self.output_dir = output_dir
        self.assets_dir = os.path.join(output_dir, "assets")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

        # Image generation setup — initialize eagerly for thread safety
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self._imagen_client = self._init_imagen_client()

    def log(self, message: str) -> None:
        """Print a log message with agent name prefix."""
        print(f"[{self.name}] {message}")

    def _init_imagen_client(self):
        """Initialize Gemini client for image generation (called once at init)."""
        if HAS_GEMINI_IMAGEN and self.gemini_api_key:
            return genai.Client(api_key=self.gemini_api_key)
        return None

    async def render(self, layout_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a slide from layout JSON.

        Args:
            layout_json: Slide layout specification with id, layout, content, style

        Returns:
            Dict with:
                - success: bool
                - slide_id: str
                - pptx_path: str (if successful)
                - image_path: str (if successful)
                - error: str (if failed)
        """
        slide_id = layout_json.get("id", "unknown")
        self.log(f"Rendering slide: {slide_id}")

        # Step 0: Prepare assets (generate images in parallel if needed)
        layout_json = await self._prepare_assets(layout_json)

        # Generate PPTX (CPU-bound, fast — keep sync)
        pptx_path = self._generate_pptx(layout_json, slide_id)

        if not pptx_path or not os.path.exists(pptx_path):
            self.log(f"Failed to generate PPTX for {slide_id}")
            return {
                "success": False,
                "slide_id": slide_id,
                "error": "PPTX generation failed"
            }

        # Convert to Image via LibreOffice (blocking subprocess → offload to thread)
        image_path = await asyncio.to_thread(self._convert_to_image, pptx_path, slide_id)

        if not image_path:
            self.log(f"Warning: Could not convert PPTX to image for {slide_id} (LibreOffice may not be installed)")
            self.log(f"PPTX was generated successfully: {pptx_path}")
        else:
            self.log(f"Successfully rendered {slide_id} with image")

        return {
            "success": True,  # PPTX generation is sufficient for success
            "slide_id": slide_id,
            "pptx_path": pptx_path,
            "image_path": image_path,  # May be None if conversion failed
            "layout_json": layout_json
        }

    def _generate_pptx(
        self,
        layout_json: Dict[str, Any],
        slide_id: str
    ) -> Optional[str]:
        """
        Generate a PPTX file from layout JSON.

        Args:
            layout_json: Slide layout specification
            slide_id: Unique slide identifier

        Returns:
            Path to generated PPTX file or None if failed
        """
        try:
            layout_json["id"] = slide_id

            # Use the slide_generator module
            pptx_path = slide_generator.generate_single_slide(
                slide_data=layout_json,
                output_dir=self.output_dir
            )

            if os.path.exists(pptx_path):
                return pptx_path
            else:
                self.log(f"Expected PPTX not found: {pptx_path}")
                return None

        except Exception as e:
            self.log(f"PPTX generation error: {e}")
            return None

    def _convert_to_image(self, pptx_path: str, slide_id: str) -> Optional[str]:
        """
        Convert a PPTX file to a PNG image using LibreOffice headless.

        Args:
            pptx_path: Path to the PPTX file
            slide_id: Unique slide identifier

        Returns:
            Path to generated image or None if failed
        """
        import shutil
        import subprocess
        import tempfile

        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            self.log("LibreOffice not found — skipping image conversion")
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = subprocess.run(
                    [libreoffice, "--headless", "--norestore", "--convert-to", "png",
                     "--outdir", tmp_dir, pptx_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                # Check for the output file first — LibreOffice can exit non-zero
                # due to harmless warnings (e.g. "failed to launch javaldx") while
                # still producing a valid PNG.
                basename = os.path.splitext(os.path.basename(pptx_path))[0]
                tmp_img = os.path.join(tmp_dir, f"{basename}.png")
                if not os.path.exists(tmp_img):
                    self.log(f"LibreOffice conversion failed: {result.stderr.strip()}")
                    return None

                dest_path = os.path.join(self.output_dir, f"{slide_id}.png")
                shutil.move(tmp_img, dest_path)
                self.log(f"Image saved: {dest_path}")
                return dest_path
        except Exception as e:
            self.log(f"Image conversion error: {e}")
            return None

    async def _prepare_assets(self, layout_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan layout for missing images with prompts and generate them in parallel.

        Args:
            layout_json: Layout specification that may contain image elements

        Returns:
            Updated layout_json with generated image paths
        """
        content = layout_json.get("content", {})
        # content may be a plain string for non-custom layouts — no image elements to process
        if not isinstance(content, dict):
            return layout_json
        elements = content.get("elements", [])

        if not elements:
            return layout_json

        # First pass: resolve cache hits synchronously, collect items that need generation
        pending: list[tuple[int, str, str, str]] = []  # (elem_index, prompt, aspect_ratio, output_path)

        for i, elem in enumerate(elements):
            if elem.get("type") != "image":
                continue
            prompt = elem.get("prompt")
            path = elem.get("path")
            if not (prompt and (not path or not os.path.exists(path))):
                continue

            aspect_ratio = _pick_aspect_ratio(elem.get("w", 16), elem.get("h", 9))
            cache_key = f"{prompt}|{aspect_ratio}"
            p_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
            generated_path = os.path.join(self.assets_dir, f"{p_hash}.png")

            if os.path.exists(generated_path):
                self.log(f"Using cached image: {generated_path}")
                elements[i]["path"] = generated_path
            else:
                self.log(f"Need to generate image for prompt: '{prompt[:50]}...' (aspect_ratio={aspect_ratio})")
                pending.append((i, prompt, aspect_ratio, generated_path))

        # Second pass: generate all pending images concurrently
        if pending:
            tasks = [
                asyncio.to_thread(self._generate_image, prompt, output_path, aspect_ratio)
                for _, prompt, aspect_ratio, output_path in pending
            ]
            results = await asyncio.gather(*tasks)

            for (elem_idx, _, _, _), result_path in zip(pending, results):
                if result_path:
                    elements[elem_idx]["path"] = result_path
                else:
                    self.log("Image generation failed, element will be skipped")

        if pending:
            content["elements"] = elements
            layout_json["content"] = content

        return layout_json

    def _generate_image(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "16:9",
    ) -> Optional[str]:
        """
        Generate an image using Gemini Imagen API.

        Args:
            prompt: Text description of the image to generate
            output_path: Where to save the generated image
            aspect_ratio: One of "1:1", "9:16", "16:9", "4:3", "3:4"

        Returns:
            Path to generated image or None if failed
        """
        client = self._imagen_client

        if not client:
            self.log("Gemini client not available for image generation")
            return None

        try:
            self.log(f"Generating image with Gemini Imagen (aspect_ratio={aspect_ratio})...")

            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                ),
            )

            if response.generated_images:
                # Save the first generated image
                image = response.generated_images[0]
                image.image.save(output_path)
                self.log(f"Image saved to {output_path}")
                return output_path
            else:
                self.log("No images generated")
                return None

        except Exception as e:
            self.log(f"Image generation error: {e}")
            return None
