#!/usr/bin/env python3
"""
Designer Agent Module

Responsible for converting abstract slide prompts into concrete Layout JSON
specifications using the Gemini API.
"""

import asyncio
import json
import json_repair
import re
from typing import Dict, Any, Optional

from src.gemini_client import GeminiClient
from .prompts import DESIGNER_SYSTEM_PROMPT


class DesignerAgent:
    """
    Designer Agent that converts abstract slide prompts into concrete Layout JSON.

    Uses Gemini API for text-to-JSON generation.
    """

    def __init__(self, llm_client: GeminiClient):
        """
        Initialize the Designer Agent.

        Args:
            llm_client: GeminiClient instance for LLM inference
        """
        self.llm = llm_client
        self.name = "designer"

    def log(self, message: str) -> None:
        """Print a log message with agent name prefix."""
        print(f"[{self.name}] {message}")

    async def design_layout(self, slide_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a concrete layout JSON from abstract slide data.

        Args:
            slide_data: Abstract slide description with id, content hints, etc.

        Returns:
            Concrete layout JSON or None if generation fails
        """
        slide_id = slide_data.get("id", "unknown")
        self.log(f"Designing layout for slide: {slide_id}")

        user_prompt = "\n".join([
            "",
            "Please design the layout for this slide:",
            "",
            f"ID: {slide_id}",
            "Input Data:",
            json.dumps(slide_data, indent=2, ensure_ascii=False),
            "",
            "Generate the concrete JSON specification.",
            ""
        ])

        # Combine system prompt with user prompt
        full_prompt = f"{DESIGNER_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            response_text = await asyncio.to_thread(
                self.llm.generate,
                full_prompt,
                temperature=0.7,
                max_tokens=8192
            )

            self.log(f"Designer response received ({len(response_text)} chars)")

            layout_json = self._extract_json(response_text)

            if layout_json:
                layout_json["id"] = slide_id
                self.log(f"Successfully generated layout for {slide_id}")
                return layout_json
            else:
                self.log(f"Failed to extract JSON for {slide_id}")
                return None

        except Exception as e:
            self.log(f"Error generating layout: {e}")
            return None

    def _extract_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON object from LLM response text.

        Args:
            response_text: Raw LLM output

        Returns:
            Parsed JSON dict or None if extraction fails
        """
        if not response_text:
            return None

        # 1. Try to extract from markdown code block
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                clean_json = json_match.group(1)
                return json_repair.loads(clean_json)
            except json.JSONDecodeError as e:
                self.log(f"Regex JSON parse error: {e}")

        # 2. Try to extract without code block markers
        clean_text = response_text.replace("```json", "").replace("```", "").strip()

        # Remove reasoning block if it exists
        clean_text = re.sub(r'<reasoning>.*?</reasoning>', '', clean_text, flags=re.DOTALL).strip()

        # Find raw JSON boundaries
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1

        if start != -1 and end > start:
            try:
                candidate = clean_text[start:end]
                return json_repair.loads(candidate)
            except json.JSONDecodeError as e:
                self.log(f"Fallback JSON parse error: {e}")
                return None

        return None
