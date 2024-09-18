import math
import os
import re
import zipfile
from django.http import HttpResponse
from django.core.files.uploadedfile import InMemoryUploadedFile

def percentile(N, percent, key=lambda x:x):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    """
    if not N:
        return None
    k = (len(N)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c-k)
    d1 = key(N[int(c)]) * (k-f)
    return d0+d1

def quantiles(N, percents):
    N = sorted(N)
    return [percentile(N, p) for p in percents]

def create_download_response(file, content_type):
    filename = os.path.basename(file.name)
    response = HttpResponse(file, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response

def make_space(text):
    return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', text)

def int_or_flot(x):
    return int(float(x)) if int(float(x)) == float(x) else float(x)


def create_zip_file(path: str, source_zip_file: str, delete_files: list[str],
                    upload_files: list[tuple[str,InMemoryUploadedFile]], texts: list[tuple[str,str]]):
    _delete_files = set(delete_files + [file_path for file_path, file in upload_files] + [file_path for file_path, text in texts])
    with zipfile.ZipFile(source_zip_file, "r") as source_zipf:
        with zipfile.ZipFile(path, "w") as target_zipf:
            # Add previous files except in delete list
            for item in source_zipf.infolist():
                if item.filename in _delete_files:
                    continue
                buffer = source_zipf.read(item.filename)
                target_zipf.writestr(item, buffer)

            # Add uploaded files
            for file_path, file_content in upload_files:
                target_zipf.writestr(file_path, file_content)

            # Add texts
            for file_path, text in texts:
                target_zipf.writestr(file_path, text)


def get_code(zip_file_path: str, path: str) -> str | None:
    try:
        with zipfile.ZipFile(zip_file_path, "r", zipfile.ZIP_DEFLATED) as zipf:
            with zipf.open(path, 'r') as f:
                return f.read().decode("utf-8")
    except (zipfile.BadZipFile, KeyError):
        return None
