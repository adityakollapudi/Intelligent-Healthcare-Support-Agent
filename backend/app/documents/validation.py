"""Upload validation (doc 06 §3.6, doc 07 §5.2 step 1). The browser's filename and MIME type are
untrusted hints: the extension, the declared type and the file's own signature must all agree, and
the content must parse within the page and pixel limits before anything is stored."""

from __future__ import annotations

import io
import re
import unicodedata
import warnings
from dataclasses import dataclass

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings
from app.core.exceptions import AppError

_EXTENSIONS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}
_PIL_FORMAT = {"image/png": "PNG", "image/jpeg": "JPEG"}
_UNSAFE_NAME = re.compile(r"[^\w.\- ()]+")


class FileTooLargeError(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"
    message = "The file is larger than the upload limit."


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"
    message = "Only PDF, PNG and JPEG files are supported, and the file type must match its extension."


class MalformedFileError(AppError):
    status_code = 422
    code = "MALFORMED_FILE"
    message = "The file could not be read as a valid document."

    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message, details=[{"field": "file", "issue": reason}])
        self.reason = reason


@dataclass(frozen=True)
class ValidatedFile:
    mime_type: str
    page_count: int
    display_name: str


def safe_display_name(filename: str | None) -> str:
    """Display-only name: last path component, control characters and unusual symbols removed."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in unicodedata.normalize("NFKC", name) if unicodedata.category(ch)[0] != "C")
    name = _UNSAFE_NAME.sub("_", name).strip(" .") or "document"
    return name[-255:]


def validate_upload(filename: str | None, declared_mime: str | None, data: bytes, settings: Settings) -> ValidatedFile:
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError(details=[{"field": "file", "issue": f"max {settings.max_upload_bytes} bytes"}])
    if not data:
        raise MalformedFileError("EMPTY_FILE", "The file is empty.")

    name = safe_display_name(filename)
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    mime = _EXTENSIONS.get(ext)
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if mime is None or declared != mime:
        raise UnsupportedFileTypeError(details=[{"field": "file", "issue": "EXTENSION_OR_TYPE_NOT_ALLOWED"}])
    if not data.startswith(_SIGNATURES[mime]):
        raise UnsupportedFileTypeError(details=[{"field": "file", "issue": "SIGNATURE_MISMATCH"}])

    pages = _check_pdf(data, settings) if mime == "application/pdf" else _check_image(data, mime, settings)
    return ValidatedFile(mime_type=mime, page_count=pages, display_name=name)


def _check_pdf(data: bytes, settings: Settings) -> int:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise MalformedFileError("ENCRYPTED_PDF", "Password-protected or encrypted PDFs aren't supported.")
            if doc.page_count < 1:
                raise MalformedFileError("NO_PAGES", "The PDF has no pages.")
            if doc.page_count > settings.max_pdf_pages:
                raise MalformedFileError(
                    "PAGE_LIMIT_EXCEEDED", f"The PDF has more than {settings.max_pdf_pages} pages."
                )
            for page in doc:  # parse every page now, so a corrupt page is rejected before storage
                page.get_text("text")
            return doc.page_count
    except MalformedFileError:
        raise
    except Exception:  # noqa: BLE001 - any parser failure means the file is malformed
        raise MalformedFileError("PDF_PARSE_ERROR") from None


def _check_image(data: bytes, mime: str, settings: Settings) -> int:
    limit = int(settings.max_image_megapixels * 1_000_000)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                if img.format != _PIL_FORMAT[mime]:
                    raise UnsupportedFileTypeError(details=[{"field": "file", "issue": "SIGNATURE_MISMATCH"}])
                width, height = img.size  # read from the header, before any pixels are decoded
                if width * height > limit:
                    raise MalformedFileError(
                        "IMAGE_TOO_LARGE", f"Images can be at most {settings.max_image_megapixels:g} megapixels."
                    )
                img.verify()
            with Image.open(io.BytesIO(data)) as img:  # verify() leaves the image unusable; decode once
                img.load()
    except (MalformedFileError, UnsupportedFileTypeError):
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise MalformedFileError("IMAGE_PARSE_ERROR") from None
    return 1
