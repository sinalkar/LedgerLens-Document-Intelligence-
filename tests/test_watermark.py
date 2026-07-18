from PIL import Image, ImageChops

from app.services.watermark import stamp


def _images():
    original = Image.new("RGB", (600, 400), "white")
    stamped = stamp(original, "doc-1234", "2026-07-18T12:00:00Z")
    return original, stamped


def test_dimensions_unchanged():
    original, stamped = _images()
    assert stamped.size == original.size


def test_bottom_right_region_differs():
    original, stamped = _images()
    w, h = original.size
    box = (w // 2, h - 40, w, h)
    diff = ImageChops.difference(original.crop(box), stamped.crop(box))
    assert diff.getbbox() is not None, "watermark left no trace in bottom-right"


def test_top_left_region_untouched():
    original, stamped = _images()
    box = (0, 0, 100, 100)
    diff = ImageChops.difference(original.crop(box), stamped.crop(box))
    assert diff.getbbox() is None
