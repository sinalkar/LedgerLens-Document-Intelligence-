from PIL import Image, ImageDraw


def stamp(img: Image.Image, doc_id: str, ts: str) -> Image.Image:
    """Provenance stamp: doc id + timestamp at ~10% opacity in the
    bottom-right corner. Dimensions are never altered."""
    out = img.copy().convert("RGBA")
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = f"{doc_id} | {ts}"
    left, top, right, bottom = draw.textbbox((0, 0), text)
    text_w, text_h = right - left, bottom - top
    w, h = out.size
    pos = (max(0, w - text_w - 10), max(0, h - text_h - 10))
    draw.text(pos, text, fill=(128, 128, 128, 26))
    return Image.alpha_composite(out, layer).convert("RGB")
