from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from .models import Participation

import os


def create_download_response(file, content_type, filename=None):
    filename = filename or os.path.basename(file.name)
    response = HttpResponse(file, content_type=content_type)
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def make_safe_filename(s):
    def safe_char(c):
        if c.isalnum():
            return c
        else:
            return "_"
    return "".join(safe_char(c) for c in s).rstrip("_")
