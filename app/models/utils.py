from django.db import models
from django.core.files.storage import default_storage

import hashlib
import re
import zipfile


class ExtraFileField(models.FileField):
    def __init__(self, verbose_name=None, name=None, upload_to='', after_file_save=None, storage=None, **kwargs):
        self.after_file_save = after_file_save
        super().__init__(verbose_name, name, upload_to=upload_to, storage=storage or default_storage, **kwargs)

    def pre_save(self, model_instance, add):
        file = super().pre_save(model_instance, add)
        if self.after_file_save is not None:
            self.after_file_save(model_instance)
        return file


def hash_file(file, block_size=65536):
    hasher = hashlib.md5()
    while True:
        data = file.read(block_size)
        if not data:
            break
        hasher.update(data)
    return hasher.hexdigest()


def compute_file_hash(instance):
    with instance.file.open():
        instance.file_hash = hash_file(instance.file)


def make_space(text):
    return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', text)


def int_or_flot(x):
    return int(float(x)) if int(float(x)) == float(x) else float(x)


def get_code(zip_file_path: str, path: str) -> str | None:
    try:
        with zipfile.ZipFile(zip_file_path, "r", zipfile.ZIP_DEFLATED) as zipf:
            with zipf.open(path, 'r') as f:
                return f.read().decode("utf-8")
    except (zipfile.BadZipFile, KeyError):
        return None
