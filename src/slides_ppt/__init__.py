"""
Slides PPT Module

A complete slide generation system using:
- Gemini API for intelligent layout design
- Programmatic rendering to PPTX and images
- Vision LLM reviewer for quality refinement

Components:
- SlidesModule_PPT: Main entry point for slide generation
- SlideOrchestrator: Coordinates Designer → Render → Reviewer pipeline
- DesignerAgent: Generates layout JSON from abstract descriptions
- RenderAgent: Converts layout JSON to PPTX and images
- ReviewerAgent: Inspects rendered images and refines layouts
"""

from .slides_ppt import SlidesModule_PPT
from .orchestrator import SlideOrchestrator
from .designer_agent import DesignerAgent
from .render_agent import RenderAgent
from .reviewer_agent import ReviewerAgent
from . import slide_generator
from . import math_renderer
from . import text_utils

__all__ = [
    "SlidesModule_PPT",
    "SlideOrchestrator",
    "DesignerAgent",
    "RenderAgent",
    "ReviewerAgent",
    "slide_generator",
    "math_renderer",
    "text_utils",
]
