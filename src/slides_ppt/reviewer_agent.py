#!/usr/bin/env python3
"""
Reviewer Agent Module

Inspects a rendered slide image with a vision-capable LLM and returns a
quality score + optional refined layout JSON. Strongly biased toward approval
(default threshold = 9/10) so only genuinely broken slides are refined.
"""

import asyncio
import json
import json_repair
import re
from typing import Dict, Any, Optional

from src.gemini_client import GeminiClient


REVIEWER_SYSTEM_PROMPT = """\
You are a professional slide design reviewer for presentation slides.
Your job is to look at the rendered slide image and judge its visual quality.

Evaluate five dimensions:
1. Composition  — elements are balanced and well-positioned on the canvas
2. Typography   — font sizes are readable; visual hierarchy is clear
3. Color        — sufficient contrast; colors are harmonious and on-brand
4. Clarity      — information is easy to absorb at a glance
5. Polish       — no clipping, no overflow, no visual artifacts

Score the slide from 1 to 10:
  9–10 : Excellent. No changes needed.
  7–8  : Good. Minor imperfections, but overall acceptable.
  5–6  : Needs improvement. Clear but with noticeable issues.
  3–4  : Poor. Major problems that hurt readability.
  1–2  : Unusable. Completely broken layout.

IMPORTANT RULES:
- A score of 9 or higher means the slide is APPROVED. Set "approved": true
  and "refined_layout": null. Do NOT propose changes for approved slides.
- Only a score below 9 warrants refinement.
- When you do return a refined_layout, make targeted fixes only — preserve
  the original content intent. Do not change text content.
- If the slide is good but not perfect, round up. Err on the side of approval.
- Return ONLY valid JSON. No markdown fences. No preamble. No extra text.

Output format (strict JSON):
{
  "score": <number 1–10>,
  "approved": <true|false>,
  "reason": "<one sentence verdict>",
  "issues": ["<specific issue>", ...],
  "refined_layout": <full layout JSON object, or null>
}"""


class ReviewerAgent:
    """
    Reviewer Agent that inspects rendered slide images and returns quality scores.

    Uses vision-capable LLM to evaluate composition, typography, color, clarity,
    and polish. Strongly biased toward approval via high default threshold.
    """

    def __init__(self, llm_client: GeminiClient, score_threshold: float = 9.0):
        """
        Initialize the Reviewer Agent.

        Args:
            llm_client: GeminiClient instance for multimodal inference
            score_threshold: Minimum score to approve (default 9.0)
        """
        self.llm = llm_client
        self.score_threshold = score_threshold
        self.name = "reviewer"

    def log(self, message: str) -> None:
        """Print a log message with agent name prefix."""
        print(f"[{self.name}] {message}")

    async def review(
        self,
        image_path: str,
        layout_json: Dict[str, Any],
        original_prompt: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Review a rendered slide image against its layout JSON.

        Args:
            image_path: Path to the rendered JPG slide image
            layout_json: The current layout JSON used to render the slide
            original_prompt: The original abstract slide description

        Returns:
            {
              "score": float,                    # 1–10
              "approved": bool,                  # score >= threshold
              "reason": str,                     # one-line verdict
              "issues": [str],                   # empty if approved
              "refined_layout": Optional[Dict]   # None if approved
            }
        """
        _fallback = {
            "score": 10,
            "approved": True,
            "reason": "parse error, assuming OK",
            "issues": [],
            "refined_layout": None,
        }

        user_prompt = "\n".join([
            "Original slide description:",
            json.dumps(original_prompt, indent=2, ensure_ascii=False),
            "",
            "Current layout JSON:",
            json.dumps(layout_json, indent=2, ensure_ascii=False),
            "",
            'Canvas: 13.33" × 7.5" (16:9). Safe area: x ∈ [0.5, 12.83], y ∈ [0.5, 7.0], units = inches.',
            "",
            "Review the rendered slide image and return your JSON verdict.",
        ])

        full_prompt = REVIEWER_SYSTEM_PROMPT + "\n\n" + user_prompt

        try:
            response_text = await asyncio.to_thread(
                self.llm.generate_with_image,
                full_prompt,
                image_path,
                temperature=0.3,
                max_tokens=8192,
            )

            self.log(f"Review response received ({len(response_text)} chars)")
            result = self._parse_response(response_text)

            # Enforce threshold logic — model may score 9.0 but set approved=False
            score = float(result.get("score", 10))
            result["approved"] = score >= self.score_threshold

            return result

        except Exception as e:
            self.log(f"Error during review: {e}")
            return _fallback

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse reviewer JSON response with fail-open fallback.

        Args:
            response_text: Raw LLM output

        Returns:
            Parsed review dict, or fallback approved result on any parse failure
        """
        _fallback = {
            "score": 10,
            "approved": True,
            "reason": "parse error, assuming OK",
            "issues": [],
            "refined_layout": None,
        }

        if not response_text:
            return _fallback

        # Strip markdown fences if present
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            candidate = json_match.group(1)
        else:
            clean = response_text.replace("```json", "").replace("```", "").strip()
            clean = re.sub(r'<reasoning>.*?</reasoning>', '', clean, flags=re.DOTALL).strip()
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start == -1 or end <= start:
                return _fallback
            candidate = clean[start:end]

        try:
            parsed = json_repair.loads(candidate)
        except Exception:
            return _fallback

        if not isinstance(parsed, dict):
            return _fallback

        required = {"score", "approved", "reason"}
        if not required.issubset(parsed.keys()):
            return _fallback

        # Ensure issues list exists
        if "issues" not in parsed:
            parsed["issues"] = []

        # Ensure refined_layout key exists
        if "refined_layout" not in parsed:
            parsed["refined_layout"] = None

        return parsed
