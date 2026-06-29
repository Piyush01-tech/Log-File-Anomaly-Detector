"""
dashboard/forms.py — Phase 10
================================
Django form definitions for the dashboard.

FORMS:
  EVTXUploadForm — File upload form for .evtx files with validation.

DESIGN DECISIONS:
  - Separate form (not ModelForm) to decouple upload validation from
    model internals. The view handles AnalysisJob creation.
  - File extension validation happens at the form level (client-facing
    error messages) AND at the model level (FileExtensionValidator on
    AnalysisJob.file_path) for defense-in-depth.
  - File size validation uses Django settings.EVTX_MAX_UPLOAD_SIZE
    to enforce configurable limits.
  - Bootstrap 5 styling applied via widget attrs for consistency
    with existing auth forms.

SECURITY:
  - Extension whitelist: only .evtx allowed.
  - File size limit: configurable, default 50MB.
  - CSRF enforced by Django middleware (not form responsibility).
  - File content is NOT validated here — Flask's EVTXFileParser
    handles binary validation downstream.
"""

import logging
from typing import Any

from django import forms
from django.conf import settings

logger = logging.getLogger(__name__)

# Default maximum upload size: 50 MB
DEFAULT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB in bytes


class EVTXUploadForm(forms.Form):
    """
    Form for uploading .evtx files for ML anomaly analysis.

    FIELDS:
      evtx_file — FileField with .evtx extension validation.

    VALIDATION:
      1. File extension must be .evtx (case-insensitive).
      2. File size must not exceed EVTX_MAX_UPLOAD_SIZE setting.
      3. File must not be empty (0 bytes).

    Usage:
        form = EVTXUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["evtx_file"]
    """

    evtx_file = forms.FileField(
        label="Windows Event Log File",
        help_text="Upload a .evtx file for anomaly analysis.",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".evtx",
                "id": "evtx-file-input",
            }
        ),
    )

    def _get_max_upload_size(self) -> int:
        """Get the maximum upload size from Django settings."""
        return getattr(
            settings, "EVTX_MAX_UPLOAD_SIZE", DEFAULT_MAX_UPLOAD_SIZE
        )

    def _format_file_size(self, size_bytes: int) -> str:
        """Format bytes into a human-readable string."""
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        if size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes} bytes"

    def clean_evtx_file(self) -> Any:
        """
        Validate the uploaded .evtx file.

        Checks:
          1. File extension is .evtx (case-insensitive).
          2. File is not empty (0 bytes).
          3. File size does not exceed the configured maximum.

        Returns:
            The validated UploadedFile object.

        Raises:
            forms.ValidationError: If any validation check fails.
        """
        uploaded_file = self.cleaned_data.get("evtx_file")

        if not uploaded_file:
            raise forms.ValidationError("Please select a file to upload.")

        # --- Extension validation ---
        filename = uploaded_file.name
        if not filename.lower().endswith(".evtx"):
            logger.warning(
                "Upload rejected: invalid extension '%s'.", filename
            )
            raise forms.ValidationError(
                "Invalid file type. Only .evtx (Windows Event Log) "
                "files are accepted."
            )

        # --- Empty file check ---
        if uploaded_file.size == 0:
            logger.warning("Upload rejected: empty file '%s'.", filename)
            raise forms.ValidationError(
                "The uploaded file is empty. Please select a valid "
                ".evtx file."
            )

        # --- File size validation ---
        max_size = self._get_max_upload_size()
        if uploaded_file.size > max_size:
            max_size_str = self._format_file_size(max_size)
            file_size_str = self._format_file_size(uploaded_file.size)
            logger.warning(
                "Upload rejected: file '%s' (%s) exceeds maximum size (%s).",
                filename,
                file_size_str,
                max_size_str,
            )
            raise forms.ValidationError(
                f"File size ({file_size_str}) exceeds the maximum "
                f"allowed size of {max_size_str}."
            )

        logger.debug(
            "Upload validation passed: '%s' (%s).",
            filename,
            self._format_file_size(uploaded_file.size),
        )

        return uploaded_file
