from django import forms
from django.forms.widgets import HiddenInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.files import File
from bootstrap_datepicker_plus.widgets import DateTimePickerInput
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Fieldset
from aicon.settings import TASK_BASE_ZIPFILE, TASK_BASE_MAIN_DIR, TASK_BASE_MAIN_FILE, TASK_BASE_SETUP_FILE, \
                           SUBMISSION_BASE_ZIPFILE, SUBMISSION_BASE_MAIN_DIR, SUBMISSION_BASE_MAIN_FILE
from .models import Invitation, Task, Submission, Course
from .utils import create_zip_file, get_code
import io
import os
import tempfile
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


class TaskFormConfig:
    TASK_LAYOUT  = [
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
    ]
    LABELS = {
        "max_upload_size": "Max upload size (KB)",
        "run_time_limit": "Run time limit (Second)",
        "memory_limit": "Memory limit (KB)",
        "partition": "Cluster partition",
        "gpus": "Cluster GPUs (examples: 1, a100:1)",
    }
    WIDGETS = {
        'opened_at': DateTimePickerInput(),
        'deadline_at': DateTimePickerInput(range_from="opened_at"),
        'closed_at': DateTimePickerInput(range_from="deadline_at"),
    }
    FIELDS = ['daily_submission_limit', 'max_upload_size', 'run_time_limit', 'memory_limit',
              'partition', 'gpus', 'opened_at', 'deadline_at', 'closed_at', 'leaderboard']


class TaskForm(forms.ModelForm):
    file = forms.FileField(required=False) # Hack for file field error

    class Meta:
        model = Task
        fields = ['name', 'description', 'file', 'template'] + TaskFormConfig.FIELDS
        labels = TaskFormConfig.LABELS
        widgets = TaskFormConfig.WIDGETS

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
            *TaskFormConfig.TASK_LAYOUT
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


class TaskCodeForm(forms.ModelForm):
    code = forms.CharField(widget=forms.Textarea)
    upload_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    template_code = forms.CharField(widget=forms.Textarea, required=False)
    template_upload_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    template_delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    setup = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Task
        fields = ['name', 'description', 'code', 'upload_files', 'delete_files', 'setup', 'template_code', 'template_upload_files', 'template_delete_files'] + TaskFormConfig.FIELDS
        labels = TaskFormConfig.LABELS
        widgets = TaskFormConfig.WIDGETS

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            'code',
            'upload_files',
            'delete_files',
            'setup',
            'template_code',
            'template_upload_files',
            'template_delete_files',
            *TaskFormConfig.TASK_LAYOUT
        )
        super().__init__(*args, **kwargs)
        self.fields["code"].initial = self.instance.code
        self.fields["setup"].initial = self.instance.setup
        self.fields["template_code"].initial = self.instance.template_code
        self.fields["delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in self.instance.file_contents]
        self.fields["template_delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in self.instance.template_file_contents]


    def save(self, commit=True):
        instance = super().save(commit=False)
        name = self.cleaned_data.get('name', False)
        code = self.cleaned_data.get('code', False)
        setup = self.cleaned_data.get('setup', False)
        upload_files = [(os.path.join(TASK_BASE_MAIN_DIR, file.name), file.read())
                        for file in self.cleaned_data.get('upload_files', False)]
        delete_files = self.cleaned_data.get('delete_files')
        texts = [(TASK_BASE_MAIN_FILE, code), (TASK_BASE_SETUP_FILE, setup)]

        template_code = self.cleaned_data.get('template_code', False)
        template_upload_files = [(os.path.join(SUBMISSION_BASE_MAIN_DIR, file.name), file.read())
                                for file in self.cleaned_data.get('template_upload_files', False)]
        template_delete_files = self.cleaned_data.get('template_delete_files')
        template_texts = [(SUBMISSION_BASE_MAIN_FILE, template_code)]

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as code_tmpf, \
             tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as template_tmpf:
            create_zip_file(code_tmpf.name, self.instance.file_path or TASK_BASE_ZIPFILE, delete_files=delete_files, upload_files=upload_files, texts=texts)
            create_zip_file(template_tmpf.name,self.instance.template_file_path or  SUBMISSION_BASE_ZIPFILE, delete_files=template_delete_files, upload_files=template_upload_files, texts=template_texts)
            with open(code_tmpf.name, "rb") as code_f, open(template_tmpf.name, "rb") as template_f:
                instance.file = File(code_f, name=f"{name}.zip")
                instance.template = File(template_f, name=f"{name}.zip")
                if commit:
                    instance.save()
                return instance


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

    class Meta:
        model = Submission
        fields = ['code', 'source_zip_file', 'upload_files', 'delete_files', 'description']

    def __init__(self, *args, base_submission: Submission, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_zip_file = base_submission.file_path
        self.fields["delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in base_submission.file_contents]

    def save(self, commit=True):
        instance = super().save(commit=False)
        unique_id = namesgenerator.get_random_name()
        code = self.cleaned_data.get('code', False)
        upload_files = [(os.path.join(Submission.MAIN_DIR, file.name), file.read())
                        for file in self.cleaned_data.get('upload_files', False)]
        delete_files = self.cleaned_data.get('delete_files')

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as tmpf:
            create_zip_file(tmpf.name, self.source_zip_file, delete_files=delete_files, upload_files=upload_files, texts=[(Submission.MAIN_FILE, code)])
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
