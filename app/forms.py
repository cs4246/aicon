from django import forms
from django.forms.widgets import HiddenInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from bootstrap_datepicker_plus import DateTimePickerInput
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from .models import Invitation, Task, Submission, Course
import io

class HideableForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        hidden = kwargs.pop('hidden', False)
        super().__init__(*args, **kwargs)
        if hidden:
            for fieldname in self.Meta.fields:
                self.fields[fieldname].widget = HiddenInput()

class TaskForm(forms.ModelForm):
    file = forms.FileField(required=False) # Hack for file field error

    class Meta:
        model = Task
        fields = ['name', 'description', 'file', 'template', 'template_file', 'daily_submission_limit', 'max_upload_size', 'run_time_limit', 'max_image_size', 'opened_at', 'deadline_at', 'closed_at', 'leaderboard']
        labels = {
            "max_upload_size": "Max upload size (KB)",
            "run_time_limit": "Run time limit (Second)",
            "max_image_size": "Max container image size (KB)",
        }
        widgets = {
            'opened_at': DateTimePickerInput().start_of('open range'),
            'deadline_at': DateTimePickerInput().end_of('open range'),
            'closed_at': DateTimePickerInput().end_of('open range'),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            'file',
            Row(
                Column('daily_submission_limit', css_class='col-3'),
                Column('max_upload_size', css_class='col-3'),
                Column('run_time_limit', css_class='col-3'),
                Column('max_image_size', css_class='col-3'), css_class="row"),
            Row(
                Column('opened_at', css_class='col-4'),
                Column('deadline_at', css_class='col-4'),
                Column('closed_at', css_class='col-4'), css_class="row"),
            Row(
                Column('template', css_class='col-6'),
                Column('template_file', css_class='col-6'), css_class="row"),
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
    runner = forms.ChoiceField(choices=Submission.RUNNERS)

    class Meta:
        model = Submission
        fields = ['runner', 'file', 'docker', 'metadata', 'description']
        labels = {
            "file": "File (.zip)",
        }
        widgets = {
            'file': forms.FileInput(attrs={'accept':'application/zip', 'class': 'clearablefileinput form-control'}),
            'metadata': forms.Textarea(attrs={'rows': 4})
        }

    def show_file_error(self):
        # Hack: fix inherent bug error not showing on file field
        self.fields['file'].widget.attrs['class'] =  'clearablefileinput form-control is-invalid'

    def clean(self):
        cleaned_data = super(SubmissionForm, self).clean()
        docker = cleaned_data.get('docker', False)
        file = cleaned_data.get('file', False)
        runner = cleaned_data.get('runner', False)
        if not docker and runner == Submission.RUNNER_DOCKER:
            raise forms.ValidationError({'docker': 'Docker required for Docker runner.'}, code='docker_required')
        if not file and runner == Submission.RUNNER_PYTHON:
            self.show_file_error()
            raise forms.ValidationError({'file': 'File required for Python runner.'}, code='file_required')

    def clean_file(self):
        SUPPORTED_FILETYPES = ['application/zip', 'application/zip-compressed', 'application/x-zip-compressed', 'multipart/x-zip']
        file = self.cleaned_data.get('file', False)
        if file:
            message = None
            if file.size > self.instance.task.max_upload_size * 1024:
                message = "File size is too large ({}KB > {}KB).".format(round(file.size/1024), self.instance.task.max_upload_size)
            if file.content_type not in SUPPORTED_FILETYPES:
                message = "File type: {} is not supported.".format(file.content_type)
            if message:
                self.show_file_error()
                raise forms.ValidationError(message, code='file_requirement_error')
        return file


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
