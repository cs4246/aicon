from django import forms
from django.forms.widgets import HiddenInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.files import File
from django.utils.crypto import get_random_string
from bootstrap_datepicker_plus.widgets import DateTimePickerInput
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Fieldset
from .models import Invitation, Task, Submission, Course
import io
import os
import zipfile
import tempfile
import shutil
import namesgenerator


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


class TaskForm(forms.ModelForm):
    file = forms.FileField(required=False) # Hack for file field error

    class Meta:
        model = Task
        fields = ['name', 'description', 'file', 'template', 'daily_submission_limit', 'max_upload_size', 'run_time_limit', 'memory_limit', 'partition', 'gpus', 'opened_at', 'deadline_at', 'closed_at', 'leaderboard']
        labels = {
            "max_upload_size": "Max upload size (KB)",
            "run_time_limit": "Run time limit (Second)",
            "memory_limit": "Memory limit (KB)",
            "partition": "Cluster partition",
            "gpus": "Cluster GPUs (examples: 1, a100:1)",
        }
        widgets = {
            'opened_at': DateTimePickerInput(),
            'deadline_at': DateTimePickerInput(range_from="opened_at"),
            'closed_at': DateTimePickerInput(range_from="deadline_at"),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Task',
                'name',
                'file',
                'template',
                'description',
            ),
            Fieldset(
                'Limit',
                Row(
                    Column('daily_submission_limit', css_class='col-3'),
                    Column('run_time_limit', css_class='col-3'),
                    Column('memory_limit', css_class='col-3'),
                    Column('max_upload_size', css_class='col-3'),
                    css_class="row"
                ),
            ),
            Fieldset(
                'Cluster',
                Row(
                    Column('partition', css_class='col-6'),
                    Column('gpus', css_class='col-6'),
                    css_class="row"
                ),
            ),
            Fieldset(
                'Timing',
                Row(
                    Column('opened_at', css_class='col-4'),
                    Column('deadline_at', css_class='col-4'),
                    Column('closed_at', css_class='col-4'),
                    css_class="row"
                ),
            ),
            'leaderboard',
            Submit('submit', 'Submit', css_class="btn btn-success")
        )
        super().__init__(*args, **kwargs)

    def show_file_error(self):
        # Hack: fix inherent bug error not showing on file field
        self.fields['file'].widget.attrs['class'] =  'clearablefileinput form-control is-invalid'

    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        error = None
        if not file:
            error = "File is required."
        if file and isinstance(file, io.BytesIO) and file.content_type != 'application/zip':
            error = "File type is not supported."
        if error:
            self.show_file_error()
            raise forms.ValidationError(error, code='file_requirement_error')
        return file


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file', 'description']
        labels = {
            "file": "File (.zip)",
        }
        widgets = {
            'file': forms.FileInput(attrs={'accept':'application/zip', 'class': 'clearablefileinput form-control'}),
        }

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
    source_zip_file = forms.CharField(widget=forms.HiddenInput(), required=False)
    upload_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, base_submission=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_zip_file = None
        if base_submission is not None:
            self.source_zip_file = base_submission.file_path
            self.fields["delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in base_submission.file_contents]
        if self.source_zip_file is None:
            self.source_zip_file = self.instance.task.template or Submission.TEMPLATE_ZIP_FILE
            self.fields["delete_files"].choices = []

    class Meta:
        model = Submission
        fields = ['code', 'source_zip_file', 'upload_files', 'delete_files', 'description']

    def save(self, commit=True):
        instance = super().save(commit=False)
        unique_id = namesgenerator.get_random_name()
        code = self.cleaned_data.get('code', False)
        upload_files = self.cleaned_data.get('upload_files', False)
        delete_files = [Submission.MAIN_FILE] + self.cleaned_data.get('delete_files') # Remove main file otherwise there will be duplicates

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as tmpf:
            with zipfile.ZipFile(self.source_zip_file, "r") as source_zipf:
                with zipfile.ZipFile(tmpf.name, "w") as target_zipf:
                    # Add previous files except in delete list
                    for item in source_zipf.infolist():
                        if item.filename in delete_files:
                            continue
                        buffer = source_zipf.read(item.filename)
                        target_zipf.writestr(item, buffer)

                    # Add uploaded files
                    for file in upload_files:
                        target_zipf.writestr(os.path.join(Submission.MAIN_DIR, file.name), file.read())

                    # Add main file
                    target_zipf.writestr(Submission.MAIN_FILE, code)

            with open(tmpf.name, "rb") as f:
                instance.file = File(f, name=f"{unique_id}.zip")
                if commit:
                    instance.save()
                return instance


class CourseForm(HideableForm):
    class Meta:
        model = Course
        fields = ('code', 'academic_year', 'semester')


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label = "Email")
    first_name = forms.CharField(label = "First name")
    last_name = forms.CharField(label = "Last name")

    class Meta:
        model = User
        labels = {
            "username": "Student ID (AXXXXXXXX)",
        }
        fields = ("username", "email", "first_name", "last_name")


class InvitationForm(HideableForm):
    class Meta:
        model = Invitation
        fields = ('key',)


class CourseJoinForm(forms.Form):
    invitation_key = forms.CharField(max_length=255, label="Invitation Key")
