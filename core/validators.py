"""
Reusable validators shared across apps.

Keeping validators here avoids duplication and makes them easy to unit-test
without pulling in the full model layer.
"""

import os
from django.core.exceptions import ValidationError
from django.conf import settings


# ─── File validators ───────────────────────────────────────────────────────────

ALLOWED_EXCEL_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",  # XLSX files are zip archives; some magic libs report this
}

ALLOWED_EXCEL_EXTENSIONS = {".xlsx"}


def validate_excel_file(file) -> None:
    """
    Validate an uploaded Excel file by both extension and MIME type (magic bytes).

    Extension checking alone is trivially bypassed by renaming a file.
    Magic-byte checking reads the actual file header regardless of the name.

    Raises ValidationError if the file is invalid.
    """
    # Check extension
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        raise ValidationError(
            f"Only .xlsx files are accepted. You uploaded a '{ext}' file."
        )

    # Check file size
    max_bytes = getattr(settings, "EXCEL_UPLOAD_MAX_MB", 5) * 1024 * 1024
    if file.size > max_bytes:
        max_mb = getattr(settings, "EXCEL_UPLOAD_MAX_MB", 5)
        raise ValidationError(
            f"File is too large ({file.size / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {max_mb} MB."
        )

    # Check magic bytes (actual file content)
    try:
        import magic  # python-magic; requires the native libmagic library

        file.seek(0)
        header = file.read(8)
        file.seek(0)
        mime = magic.from_buffer(header, mime=True)
        if mime not in ALLOWED_EXCEL_MIME_TYPES:
            raise ValidationError(
                f"File content does not match an Excel file (detected: {mime}). "
                "Please upload a valid .xlsx file."
            )
    except ValidationError:
        raise
    except Exception:
        # If python-magic is unavailable or fails, log and proceed.
        # Extension check above still provides a basic guard.
        import logging
        logging.getLogger(__name__).warning(
            "python-magic unavailable; skipping MIME type check for %s", file.name
        )
