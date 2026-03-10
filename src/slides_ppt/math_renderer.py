#!/usr/bin/env python3
"""
Math Renderer Module

Renders LaTeX mathematical equations as PNG images for embedding in slides.
Uses matplotlib's native LaTeX rendering engine.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib import mathtext


class MathRenderer:
    """Render LaTeX math equations to PNG images."""

    def __init__(self, cache_dir: str = None):
        """
        Initialize the Math Renderer.

        Args:
            cache_dir: Directory to cache rendered images (default: ./math_cache)
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("tmp/math_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def render_latex(
        self,
        latex: str,
        font_size: int = 24,
        color: str = "#000000",
        dpi: int = 300,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Render a LaTeX math expression to PNG.

        Args:
            latex: LaTeX math string (e.g., "E = mc^2" or "\\frac{1}{2}")
            font_size: Font size in points
            color: Text color in hex format
            dpi: Resolution in dots per inch
            output_path: Custom output path (if None, uses cache)

        Returns:
            Path to the generated PNG file, or None if rendering failed
        """
        try:
            # Normalize LaTeX (ensure it's in math mode)
            latex_normalized = self._normalize_latex(latex)

            # Generate cache key
            cache_key = self._generate_cache_key(latex_normalized, font_size, color, dpi)

            # Check cache first
            if output_path is None:
                output_path = str(self.cache_dir / f"{cache_key}.png")
                if os.path.exists(output_path):
                    return output_path

            # Render the equation
            self._render_to_file(latex_normalized, output_path, font_size, color, dpi)

            return output_path

        except Exception as e:
            print(f"Math rendering error: {e}")
            print(f"LaTeX string: {latex}")
            return None

    def _normalize_latex(self, latex: str) -> str:
        """
        Normalize LaTeX string to ensure proper math mode.

        Args:
            latex: Raw LaTeX string

        Returns:
            Normalized LaTeX with proper delimiters
        """
        latex = latex.strip()

        # If already in display math mode, keep it
        if latex.startswith('$$') and latex.endswith('$$'):
            return latex

        # If in inline math mode, convert to display
        if latex.startswith('$') and latex.endswith('$'):
            return '$' + latex + '$'

        # If no math delimiters, add them
        return f'${latex}$'

    def _generate_cache_key(
        self,
        latex: str,
        font_size: int,
        color: str,
        dpi: int
    ) -> str:
        """Generate a unique cache key for the rendered equation."""
        content = f"{latex}|{font_size}|{color}|{dpi}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _render_to_file(
        self,
        latex: str,
        output_path: str,
        font_size: int,
        color: str,
        dpi: int
    ):
        """
        Actually render the LaTeX to a PNG file using matplotlib.

        Args:
            latex: Normalized LaTeX string
            output_path: Where to save the PNG
            font_size: Font size in points
            color: Hex color code
            dpi: Resolution
        """
        # Convert hex color to RGB tuple
        rgb = self._hex_to_rgb(color)

        # Create figure with transparent background
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0.0)

        try:
            # Render the math text
            text = fig.text(
                0.5, 0.5,
                latex,
                fontsize=font_size,
                color=rgb,
                ha='center',
                va='center',
                transform=fig.transFigure
            )

            # Get tight bounding box
            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer())
            bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())

            # Expand bbox slightly for padding
            bbox_inches = bbox_inches.padded(0.1)

            # Save with tight bbox
            plt.savefig(
                output_path,
                dpi=dpi,
                bbox_inches=bbox_inches,
                transparent=True,
                format='png',
                pad_inches=0
            )

        finally:
            plt.close(fig)

    def _hex_to_rgb(self, hex_color: str) -> Tuple[float, float, float]:
        """
        Convert hex color to RGB tuple (0-1 range).

        Args:
            hex_color: Hex color string like "#FF0000"

        Returns:
            RGB tuple with values in [0, 1]
        """
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

    def estimate_size(self, latex: str, font_size: int) -> Tuple[float, float]:
        """
        Estimate the rendered size of a LaTeX equation in inches.

        Args:
            latex: LaTeX string
            font_size: Font size in points

        Returns:
            Tuple of (width_inches, height_inches)
        """
        # Rough heuristic: scale with font size and character count
        # This is approximate - actual rendering may vary
        char_count = len(latex)
        base_width = 0.1 * font_size / 24  # Base width per character
        base_height = 0.5 * font_size / 24  # Base height

        width = base_width * char_count
        height = base_height

        # Adjust for complex expressions
        if '\\frac' in latex or '\\sum' in latex or '\\int' in latex:
            height *= 1.5
        if '\\sqrt' in latex:
            height *= 1.3

        return (width, height)
