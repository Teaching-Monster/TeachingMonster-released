from PIL import Image, ImageDraw


def add_cursor_pointer(
    img: Image.Image,
    xy: tuple[int, int],
    *,
    direction: str = "nw",          # "nw", "ne", "sw", "se" (where the arrow comes from)
    size: int = 36,                 # overall cursor size in pixels
    outline: int = 2,               # outline thickness
    fill=(255, 150, 150, 255),      # white cursor fill (r, g, b, transparency)
    stroke=(0, 0, 0, 255),          # black outline
    shadow=(0, 0, 0, 90),           # translucent shadow
    shadow_offset=(2, 2),           # shadow dx, dy
    hotspot_offset=(2, 2),          # move the "tip" slightly (often nicer than exact vertex)
) -> Image.Image:
    """
    Returns a copy of img with a cursor pointing at xy.
    Cursor is drawn in an RGBA overlay and composited onto the image.
    """
    x, y = map(int, xy)

    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    s = int(size)

    # A simple "mouse cursor" polygon in local coordinates where the TIP is at (0, 0)
    # and the cursor extends into +x/+y (like a typical NW-coming cursor).
    # Then we rotate/flip it by choosing direction.
    # Shape: a triangular arrow with a little tail notch.
    poly_local = [
        (0, 0),          # tip
        (0, s),          # down
        (int(0.28*s), int(0.72*s)),
        (int(0.45*s), int(s)),
        (int(0.62*s), int(0.88*s)),
        (int(0.43*s), int(0.64*s)),
        (int(0.92*s), int(0.55*s)),  # right
    ]

    def transform(pt):
        px, py = pt
        # Starting shape assumes cursor extends to +x/+y from tip (direction "nw" = cursor comes from NW).
        # We want the cursor to come from a given quadrant toward the point.
        if direction == "nw":      # comes from NW -> extends SE (default)
            tx, ty = px, py
        elif direction == "ne":    # comes from NE -> extend SW (mirror x)
            tx, ty = -px, py
        elif direction == "sw":    # comes from SW -> extend NE (mirror y)
            tx, ty = px, -py
        elif direction == "se":    # comes from SE -> extend NW (mirror x and y)
            tx, ty = -px, -py
        else:
            raise ValueError("direction must be one of: 'nw','ne','sw','se'")

        return (x + tx + hotspot_offset[0], y + ty + hotspot_offset[1])

    poly = [transform(p) for p in poly_local]

    # Draw shadow first (slightly offset)
    poly_shadow = [(px + shadow_offset[0], py + shadow_offset[1]) for (px, py) in poly]
    d.polygon(poly_shadow, fill=shadow)

    # Draw cursor (fill + outline)
    d.polygon(poly, fill=fill, outline=stroke)
    if outline > 1:
        # Thicken outline by redrawing slightly expanded strokes (simple approach)
        for i in range(1, outline):
            d.polygon(
                [(px+i, py) for (px, py) in poly],
                outline=stroke
            )
            d.polygon(
                [(px, py+i) for (px, py) in poly],
                outline=stroke
            )

    # Optional: a small target dot exactly at (x,y)
    r = max(2, size // 18)
    d.ellipse((x-r, y-r, x+r, y+r), fill=(255, 0, 0, 200), outline=(0, 0, 0, 180))

    out = Image.alpha_composite(base, overlay)
    return out


# --- Usage example ---
if __name__ == "__main__":
    out = add_cursor_pointer(Image.open("tmp.png"), (250, 140), direction="nw", size=40)
    out.convert("RGB").save("output_with_cursor.png")
