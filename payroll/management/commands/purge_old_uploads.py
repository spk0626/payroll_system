"""
Management command: purge_old_uploads

Deletes Excel salary files that are older than 12 months from SALARY_UPLOADS_ROOT.
The UploadBatch database record is kept (it's part of the audit trail).
Only the physical file on disk is deleted.

Usage:
    python manage.py purge_old_uploads
    python manage.py purge_old_uploads --months 6     # purge files older than 6 months
    python manage.py purge_old_uploads --dry-run      # preview without deleting

Add to cron for monthly cleanup:
    0 3 1 * * /path/to/.venv/bin/python /path/to/manage.py purge_old_uploads
"""

import os
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from payroll.models import UploadBatch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete uploaded Excel salary files older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=12,
            help="Delete files older than this many months (default: 12).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        months = options["months"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=months * 30)
        upload_root = settings.SALARY_UPLOADS_ROOT
        upload_root_path = Path(upload_root).resolve()

        old_batches = UploadBatch.objects.filter(
            created_at__lt=cutoff,
            file_path__isnull=False,
        ).exclude(file_path="")

        total = 0
        deleted = 0
        missing = 0

        for batch in old_batches:
            abs_path = (upload_root_path / batch.file_path).resolve()
            total += 1

            try:
                abs_path.relative_to(upload_root_path)
            except ValueError:
                self.stderr.write(
                    f"  Skipped unsafe path {batch.file_path} (batch {batch.pk})"
                )
                continue

            if not os.path.exists(abs_path):
                missing += 1
                continue

            if dry_run:
                self.stdout.write(f"  Would delete: {batch.file_path} (batch {batch.pk})")
            else:
                try:
                    os.remove(abs_path)
                    deleted += 1
                    logger.info("Purged upload file %s (batch %s).", batch.file_path, batch.pk)
                except OSError as exc:
                    self.stderr.write(
                        f"  Failed to delete {abs_path}: {exc}"
                    )

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Purge complete. "
                f"Eligible: {total}, "
                f"{'Would delete' if dry_run else 'Deleted'}: {total - missing}, "
                f"Already missing: {missing}."
            )
        )
