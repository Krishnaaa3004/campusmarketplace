"""PDF validation and server-side preview rendering for the Resource Hub.

Previews are the only part of a resource that leaves the server for viewers
without access, so the blur happens here, on the pixels, before anything is
written to the public uploads folder. CSS blur would ship the real page.
"""

import io
from dataclasses import dataclass

import pymupdf as fitz
from PIL import Image, ImageFilter

MAX_PDF_BYTES = 15 * 1024 * 1024
PREVIEW_PAGES = 4  # page 1 sharp + pages 2-4 blurred; nothing past this is ever rendered

SHARP_WIDTH = 1000  # px, page 1
BLUR_WIDTH = 320  # px, pages 2-4 stay small on purpose
BLUR_RADIUS = 14
# Single-page sale PDFs: blurred lower half is shrunk this much before blurring,
# so the fine detail is thrown away rather than just smoothed.
HALF_DOWNSCALE = 6


class PdfError(ValueError):
    """Raised with a user-facing message when an upload isn't an acceptable PDF."""


@dataclass
class PreviewImage:
    kind: str  # "sharp" | "blurred" | "partial"
    data: bytes  # JPEG bytes


def read_limited(fileobj, limit: int = MAX_PDF_BYTES) -> bytes:
    """Read at most limit+1 bytes so an oversized upload never sits fully in memory."""
    data = fileobj.read(limit + 1)
    if len(data) > limit:
        raise PdfError(f"PDF must be under {limit // (1024 * 1024)} MB")
    return data


def open_pdf(data: bytes) -> fitz.Document:
    """Validate raw bytes and return an open document. Raises PdfError."""
    if len(data) > MAX_PDF_BYTES:
        raise PdfError(f"PDF must be under {MAX_PDF_BYTES // (1024 * 1024)} MB")
    if not data.startswith(b"%PDF"):
        raise PdfError("That file isn't a PDF")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfError("That PDF couldn't be read. Try exporting it again.")
    if doc.needs_pass or doc.is_encrypted:
        doc.close()
        raise PdfError("Password-protected or encrypted PDFs aren't supported")
    if doc.page_count < 1:
        doc.close()
        raise PdfError("That PDF has no pages")
    return doc


def _render(page: fitz.Page, width: int) -> Image.Image:
    zoom = min(width / max(page.rect.width, 1), 3.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _heavy_blur(img: Image.Image, downscale: int = 1) -> Image.Image:
    w, h = img.size
    if downscale > 1:
        small = img.resize((max(1, w // downscale), max(1, h // downscale)), Image.BILINEAR)
        img = small.resize((w, h), Image.BILINEAR)
    return img.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))


def render_previews(doc: fitz.Document, half_blur_single_page: bool = False) -> list[PreviewImage]:
    """Page 1 sharp, pages 2-4 small and heavily blurred.

    With half_blur_single_page and a 1-page document, page 1 keeps only its top
    half sharp; the lower half is blurred so a one-page sale isn't given away.
    """
    first = _render(doc[0], SHARP_WIDTH)

    if half_blur_single_page and doc.page_count == 1:
        w, h = first.size
        cut = h // 2
        lower = _heavy_blur(first.crop((0, cut, w, h)), downscale=HALF_DOWNSCALE)
        first.paste(lower, (0, cut))
        return [PreviewImage("partial", _jpeg(first, 80))]

    out = [PreviewImage("sharp", _jpeg(first, 82))]
    for i in range(1, min(doc.page_count, PREVIEW_PAGES)):
        img = _heavy_blur(_render(doc[i], BLUR_WIDTH))
        out.append(PreviewImage("blurred", _jpeg(img, 45)))
    return out
