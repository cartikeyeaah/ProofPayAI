import base64
from io import BytesIO
from typing import Callable

from ..schemas import EvidenceDocument, MAX_TEXT, ParsedPage

# OCR receives bytes and a media type, and returns one text string per page.
OCRReader = Callable[[bytes, str], list[str]]


class DocumentError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def tesseract_image_reader(data: bytes, media_type: str) -> list[str]:
    """Optional local OCR; requires Pillow, pytesseract and the tesseract binary."""
    from PIL import Image
    import pytesseract

    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 25_000_000:
            raise DocumentError("IMAGE_TOO_LARGE")
        image.load()
        return [pytesseract.image_to_string(image, timeout=30)]


def parse_document(document: EvidenceDocument, ocr: OCRReader | None = None) -> list[ParsedPage]:
    if document.media_type == "text/plain":
        texts = [document.text or ""]
    else:
        data = base64.b64decode(document.content_base64 or "", validate=True)
        signatures = {"application/pdf": b"%PDF-", "image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
        if not data.startswith(signatures[document.media_type]):
            raise DocumentError("INVALID_FILE_SIGNATURE")
        if document.media_type == "application/pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise DocumentError("PDF_READER_UNAVAILABLE") from exc
            try:
                reader = PdfReader(BytesIO(data))
                if reader.is_encrypted:
                    raise DocumentError("ENCRYPTED_PDF")
                if len(reader.pages) > 50:
                    raise DocumentError("TOO_MANY_PAGES")
                texts = [page.extract_text() or "" for page in reader.pages]
            except DocumentError:
                raise
            except Exception as exc:
                raise DocumentError("PDF_PARSE_FAILED") from exc
            # Partial scans must not silently appear fully parsed.
            if any(not text.strip() for text in texts):
                if ocr is None:
                    raise DocumentError("PDF_OCR_REQUIRED")
                texts = _ocr(ocr, data, document.media_type)
                if len(texts) != len(reader.pages):
                    raise DocumentError("OCR_PAGE_COUNT_MISMATCH")
        else:
            if ocr is None:
                raise DocumentError("IMAGE_OCR_REQUIRED")
            texts = _ocr(ocr, data, document.media_type)
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise DocumentError("EMPTY_DOCUMENT")
    if len(texts) > 50 or sum(map(len, texts)) > MAX_TEXT:
        raise DocumentError("EXTRACTED_TEXT_TOO_LARGE")
    return [ParsedPage(document_id=document.id, page=i, text=text) for i, text in enumerate(texts, 1)]


def _ocr(ocr: OCRReader, data: bytes, media_type: str) -> list[str]:
    try:
        result = ocr(data, media_type)
        if not isinstance(result, list):
            raise DocumentError("INVALID_OCR_OUTPUT")
        return result
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("OCR_FAILED") from exc
