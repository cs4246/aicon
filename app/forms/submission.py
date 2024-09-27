from django import forms
from django.core.files import File
from crispy_forms.helper import FormHelper
from app.forms.utils import MultipleFileField, create_zip_file
from app.models import Submission

import tempfile
import namesgenerator
import os


class SubmissionPackageForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file', 'description']
        labels = {
            "file": "File (.zip)",
        }
        widgets = {
            'file': forms.FileInput(attrs={'accept':'application/zip', 'class': 'clearablefileinput form-control'}),
        }

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_id = "submission-form"
        return helper

    def clean_file(self):
        SUPPORTED_FILETYPES = ['application/zip', 'application/zip-compressed', 'application/x-zip-compressed', 'multipart/x-zip']
        file = self.cleaned_data.get('file', False)
        if not file:
            raise forms.ValidationError("File is required.", code='file_required')
        if file:
            message = None
            if file.size > self.instance.task.max_upload_size * 1024:
                message = f"File size is too large ({round(file.size/1024)}KB > {self.instance.task.max_upload_size}KB)."
            if file.content_type not in SUPPORTED_FILETYPES:
                message = f"File type: {file.content_type} is not supported."
            if message:
                raise forms.ValidationError(message, code='file_requirement_error')
        return file


class SubmissionCodeForm(forms.ModelForm):
    code = forms.CharField(widget=forms.Textarea)
    add_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Submission
        fields = ['code', 'add_files', 'delete_files', 'description']

    def __init__(self, *args, base_submission: Submission, submission_files_allowed: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_zip_file = base_submission.file_path
        self.fields["delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in base_submission.file_contents]
        if not submission_files_allowed:
            for field_name in ['add_files', 'delete_files']:
                del self.fields[field_name]

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_id = "submission-form"
        helper.attrs = {"enctype": "multipart/form-data", "novalidate": ""}
        return helper

    def save(self, commit=True):
        instance = super().save(commit=False)
        unique_id = namesgenerator.get_random_name()
        code = self.cleaned_data.get('code', False)
        add_files = [(os.path.join(Submission.MAIN_DIR, file.name), file.read())
                     for file in self.cleaned_data.get('add_files', [])]
        delete_files = self.cleaned_data.get('delete_files', [])

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as tmpf:
            create_zip_file(tmpf.name, self.source_zip_file, delete_files=delete_files, add_files=add_files, texts=[(Submission.MAIN_FILE, code)])
            with open(tmpf.name, "rb") as f:
                instance.file = File(f, name=f"{unique_id}.zip")
                if commit:
                    instance.save()
                return instance
