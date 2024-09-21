from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile

import zipfile


class HideableForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        hidden = kwargs.pop('hidden', False)
        super().__init__(*args, **kwargs)
        if hidden:
            for fieldname in self.Meta.fields:
                self.fields[fieldname].widget = HiddenInput()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs=kwargs.get("attrs")))
        kwargs.pop("attrs")
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


def create_zip_file(path: str, source_zip_file: str, delete_files: list[str],
                    add_files: list[tuple[str,InMemoryUploadedFile]], texts: list[tuple[str,str]]):
    _delete_files = set(delete_files + [file_path for file_path, file in add_files] + [file_path for file_path, text in texts])
    with zipfile.ZipFile(source_zip_file, "r") as source_zipf:
        with zipfile.ZipFile(path, "w") as target_zipf:
            # Add previous files except in delete list
            for item in source_zipf.infolist():
                if item.filename in _delete_files:
                    continue
                buffer = source_zipf.read(item.filename)
                target_zipf.writestr(item, buffer)

            # Add uploaded files
            for file_path, file_content in add_files:
                target_zipf.writestr(file_path, file_content)

            # Add texts
            for file_path, text in texts:
                target_zipf.writestr(file_path, text)
