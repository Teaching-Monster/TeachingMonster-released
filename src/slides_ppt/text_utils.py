"""
Text Utilities

Helper functions for text processing and layout calculation.
"""

from PIL import ImageFont, ImageDraw, Image


class TextFitter:
    def __init__(self, font_path=None):
        """
        Initialize TextFitter.

        Args:
            font_path: Path to a .ttf file. If None, uses Pillow's default (which is very limited).
                       Ideally should point to a standard font like Arial or Roboto.
        """
        self.font_path = font_path

    def load_font(self, size):
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except IOError:
                pass
        return ImageFont.load_default()

    def fit_text(self, text, max_width_px, max_height_px, start_size=40, min_size=8):
        """
        Calculate the optimal font size to fit text within a bounding box.

        Args:
            text: The text string.
            max_width_px: Maximum width in pixels.
            max_height_px: Maximum height in pixels.
            start_size: Starting font size (points).
            min_size: Minimum allowable font size.

        Returns:
            optimal_font_size (int)
        """
        if not text:
            return start_size

        canvas = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(canvas)

        current_size = start_size

        while current_size >= min_size:
            font = self.load_font(current_size)

            # Simple word wrap calculation
            lines = []
            words = text.split()
            current_line = []

            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]

                if w <= max_width_px:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        # Single word too long - let it overflow or truncate
                        lines.append(word)
                        current_line = []

            if current_line:
                lines.append(' '.join(current_line))

            # Calculate total height
            total_height = 0
            max_line_width = 0

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                max_line_width = max(max_line_width, w)
                total_height += h * 1.2  # Line height factor

            if total_height <= max_height_px and max_line_width <= max_width_px:
                return current_size

            current_size -= 2  # Decrease step

        # If we reach here, even min_size doesn't fit
        # Return min_size anyway, truncation will happen at render time
        return min_size

    def check_overflow(self, text, width_px, height_px, font_size):
        """
        Check if text overflows at a given font size.

        Args:
            text: The text string
            width_px: Box width in pixels
            height_px: Box height in pixels
            font_size: Font size in points

        Returns:
            dict with overflow info: {
                'overflows': bool,
                'overflow_height': float (pixels overflowing),
                'overflow_width': float,
                'needs_truncation': bool
            }
        """
        if not text:
            return {
                'overflows': False,
                'overflow_height': 0,
                'overflow_width': 0,
                'needs_truncation': False
            }

        canvas = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(canvas)
        font = self.load_font(font_size)

        # Word wrap
        lines = []
        words = text.split()
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]

            if w <= width_px:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []

        if current_line:
            lines.append(' '.join(current_line))

        # Calculate actual dimensions
        total_height = 0
        max_width = 0

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            max_width = max(max_width, w)
            total_height += h * 1.2

        overflow_h = max(0, total_height - height_px)
        overflow_w = max(0, max_width - width_px)

        return {
            'overflows': overflow_h > 0 or overflow_w > 0,
            'overflow_height': overflow_h,
            'overflow_width': overflow_w,
            'needs_truncation': overflow_h > 0
        }
