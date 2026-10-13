"""Check uploaded images by their actual contents, not the browser's word for it.

The content type and file name in an upload come from the client, so a "photo" could really
be an SVG with script, an HTML page, or a huge file. Pillow decodes the bytes; only real
JPEG/PNG/WEBP/GIF images under the size limit are accepted, and the stored type and
extension come from what Pillow found.
"""

import io

from PIL import Image, UnidentifiedImageError

# Refuse "decompression bombs": tiny files that expand to gigantic images in memory.
Image.MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
    "GIF": ("image/gif", ".gif"),
}


class ImageError(ValueError):
    """User-facing reason an upload was refused."""


def read_upload(fileobj, max_bytes: int) -> bytes:
    """Read at most max_bytes+1 so an oversized upload never sits fully in memory."""
    data = fileobj.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ImageError(f"Images must be under {max_bytes // (1024 * 1024)} MB")
    return data


def check_image(data: bytes) -> tuple[str, str]:
    """Return (content_type, extension) for a real, allowed image; raise ImageError otherwise."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ImageError("That file isn't a supported image. Use a JPG, PNG, WEBP or GIF.")
    if fmt not in ALLOWED_FORMATS:
        raise ImageError("Use a JPG, PNG, WEBP or GIF image")
    return ALLOWED_FORMATS[fmt]
