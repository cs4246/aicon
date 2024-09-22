from django import forms
from django.core.files import File
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, HTML
from bootstrap_datepicker_plus.widgets import DateTimePickerInput
from aicon.settings import TASK_BASE_ZIPFILE, TASK_BASE_MAIN_DIR, TASK_BASE_MAIN_FILE, TASK_BASE_SETUP_FILE, \
                           SUBMISSION_BASE_ZIPFILE, SUBMISSION_BASE_MAIN_DIR, SUBMISSION_BASE_MAIN_FILE
from app.forms.utils import MultipleFileField, create_zip_file
from app.models import Task

import io
import tempfile
import os


class TaskFormConfig:
    TASK_LAYOUT = [
        Div(HTML("Task"), css_class='accordion'),
        Div(
            'name',
            'description',
            Row(
                Column('opened_at', css_class='col-4'),
                Column('deadline_at', css_class='col-4'),
                Column('closed_at', css_class='col-4'),
                css_class="row"
            ),
            css_class='accordion-panel',
        ),
    ]
    SETTINGS_LAYOUT  = [
        Div(HTML("Settings"), css_class='accordion'),
        Div(
            Row(
                Column('daily_submission_limit', css_class='col-3'),
                Column('run_time_limit', css_class='col-3'),
                Column('memory_limit', css_class='col-3'),
                Column('max_upload_size', css_class='col-3'),
                css_class="row"
            ),
            Row(
                Column('partition', css_class='col-6'),
                Column('gpus', css_class='col-6'),
                css_class="row"
            ),
            'leaderboard',
            css_class='accordion-panel',
        ),
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


class TaskPackageForm(forms.ModelForm):
    file = forms.FileField(required=False) # Hack for file field error

    class Meta:
        model = Task
        fields = ['name', 'description', 'file', 'template'] + TaskFormConfig.FIELDS
        labels = TaskFormConfig.LABELS
        widgets = TaskFormConfig.WIDGETS

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_id = "task-form"
        helper.layout = Layout(
            *TaskFormConfig.TASK_LAYOUT,
            Div(HTML("Evaluation and Template Packages"), css_class='accordion'),
            Div(
                'file',
                'template',
                css_class='accordion-panel',
            ),
            *TaskFormConfig.SETTINGS_LAYOUT,
        )
        return helper

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
    add_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    template_code = forms.CharField(widget=forms.Textarea, required=False)
    template_add_files = MultipleFileField(required=False, attrs={'class': 'clearablefileinput form-control'})
    template_delete_files = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple, required=False)

    setup = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Task
        fields = ['name', 'description', 'code', 'add_files', 'delete_files', 'setup', 'template_code', 'template_add_files', 'template_delete_files'] + TaskFormConfig.FIELDS
        labels = TaskFormConfig.LABELS
        widgets = TaskFormConfig.WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].initial = self.instance.code
        self.fields["setup"].initial = self.instance.setup
        self.fields["template_code"].initial = self.instance.template_code
        self.fields["delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in self.instance.file_contents]
        self.fields["template_delete_files"].choices = [(f, "/".join(f.split('/')[1:])) for f in self.instance.template_file_contents]

    @property
    def helper(self):
        helper = FormHelper()
        helper.attrs = {"novalidate": ""}
        helper.form_id = "task-form"
        helper.layout = Layout(
            *TaskFormConfig.TASK_LAYOUT,
            Div(HTML("Setup"), css_class='accordion'),
            Div(
                'setup',
                css_class='accordion-panel',
            ),
            Div(HTML("Evaluation"), css_class='accordion'),
            Div(
                'code',
                'add_files',
                'delete_files',
                css_class='accordion-panel',
            ),
            Div(HTML("Template"), css_class='accordion'),
            Div(
                'template_code',
                'template_add_files',
                'template_delete_files',
                css_class='accordion-panel',
            ),
            *TaskFormConfig.SETTINGS_LAYOUT,
        )
        return helper

    def save(self, commit=True):
        instance = super().save(commit=False)
        name = self.cleaned_data.get('name', False)
        code = self.cleaned_data.get('code', False)
        setup = self.cleaned_data.get('setup', False)
        add_files = [(os.path.join(TASK_BASE_MAIN_DIR, file.name), file.read())
                     for file in self.cleaned_data.get('add_files', False)]
        delete_files = self.cleaned_data.get('delete_files')
        texts = [(TASK_BASE_MAIN_FILE, code), (TASK_BASE_SETUP_FILE, setup)]

        template_code = self.cleaned_data.get('template_code', False)
        template_add_files = [(os.path.join(SUBMISSION_BASE_MAIN_DIR, file.name), file.read())
                              for file in self.cleaned_data.get('template_add_files', False)]
        template_delete_files = self.cleaned_data.get('template_delete_files')
        template_texts = [(SUBMISSION_BASE_MAIN_FILE, template_code)]

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as code_tmpf, \
             tempfile.NamedTemporaryFile(suffix='.zip', delete=True) as template_tmpf:
            create_zip_file(code_tmpf.name, self.instance.file_path or TASK_BASE_ZIPFILE, delete_files=delete_files, add_files=add_files, texts=texts)
            create_zip_file(template_tmpf.name,self.instance.template_file_path or  SUBMISSION_BASE_ZIPFILE, delete_files=template_delete_files, add_files=template_add_files, texts=template_texts)
            with open(code_tmpf.name, "rb") as code_f, open(template_tmpf.name, "rb") as template_f:
                instance.file = File(code_f, name=f"{name}.zip")
                instance.template = File(template_f, name=f"{name}.zip")
                if commit:
                    instance.save()
                return instance
