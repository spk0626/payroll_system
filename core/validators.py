"""
Reusable validators shared across apps.

Keeping validators here avoids duplication and makes them easy to unit-test
without pulling in the full model layer.
"""

import os
import zipfile
from django.core.exceptions import ValidationError
from django.conf import settings


# ─── File validators ───────────────────────────────────────────────────────────

ALLOWED_EXCEL_EXTENSIONS = {".xlsx"}


def validate_excel_file(file) -> None:
    """
    Validate an uploaded Excel file by extension, size, and XLSX structure.

    Extension checking alone is trivially bypassed by renaming a file.
    XLSX files are ZIP archives with known workbook entries, so inspect that
    structure directly instead of relying on server-dependent MIME detection.

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

    # Check actual XLSX structure. On shared hosting, python-magic may report
    # valid .xlsx files as application/octet-stream, so avoid MIME detection.
    try:
        file.seek(0)
        with zipfile.ZipFile(file) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise ValidationError(
                    "File content does not match an Excel workbook. "
                    "Please upload a valid .xlsx file."
                )
    except zipfile.BadZipFile:
        raise ValidationError(
            "File content does not match an Excel workbook. "
            "Please upload a valid .xlsx file."
        )
    finally:
        try:
            file.seek(0)
        except Exception:
            pass
