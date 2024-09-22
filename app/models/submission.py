from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.shortcuts import reverse
from django.core.files.base import ContentFile
from aicon.settings import SUBMISSION_BASE_ZIPFILE, SUBMISSION_BASE_MAIN_DIR, SUBMISSION_BASE_MAIN_FILE
from pathlib import Path
from app.models.task import Task
from app.models.suggestion import Suggestion
from app.models.utils import make_space, int_or_flot, get_code
from app.utils import make_safe_filename

import re
import zipfile
import os
import json


def submission_path(instance, filename):
    return 'courses/{}/tasks/{}/submissions/{}/{}'.format(
        instance.task.course.id, make_safe_filename(instance.task.name), instance.user.id, filename
    )


class Submission(models.Model):
    MAIN_DIR = SUBMISSION_BASE_MAIN_DIR
    MAIN_FILE = SUBMISSION_BASE_MAIN_FILE
    TEMPLATE_ZIP_FILE = SUBMISSION_BASE_ZIPFILE

    STATUS_QUEUED = 'Q'
    STATUS_RUNNING = 'R'
    STATUS_ERROR = 'E'
    STATUS_DONE = 'D'
    STATUSES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_ERROR, 'Error'),
        (STATUS_DONE, 'Done')
    ]

    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=submission_path, blank=True, null=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions')

    status = models.CharField(
        max_length=1,
        choices=STATUSES,
        default=STATUS_QUEUED,
    )
    point = models.DecimalField(max_digits=9, decimal_places=3, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)

    @classmethod
    def get_code(cls, path):
        return get_code(path, cls.MAIN_FILE)

    @property
    def name(self):
        return Path(self.filename).stem if self.filename else None

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else None

    @property
    def file_url(self):
        return reverse('submission_download', args=(self.task.course.pk,self.task.pk, self.pk))

    @property
    def file_path(self):
        if not self.file or not os.path.exists(self.file.path):
            return None
        try:
            with zipfile.ZipFile(self.file.path, "r", zipfile.ZIP_DEFLATED) as zipf:
                zipf.read(self.MAIN_FILE)
            return self.file.path
        except (zipfile.BadZipFile, KeyError):
            return None

    @property
    def file_size(self):
        try:
            return self.file.size
        except Exception:
            return None

    @property
    def files(self):
        if self.file_path is None:
            return []
        with zipfile.ZipFile(self.file_path, "r", zipfile.ZIP_DEFLATED) as zipf:
            files = []
            for filename in self.file_content_names:
                with zipf.open(filename, 'r') as f:
                    files.append(ContentFile(f.read(), name=filename))
            return files

    @property
    def file_content_names(self):
        if self.file_path is None:
            return []
        with zipfile.ZipFile(self.file.path, "r", zipfile.ZIP_DEFLATED) as zipf:
            return zipf.namelist()

    @property
    def file_contents(self):
        return [m for m in self.file_content_names if re.match(r".+\/.+", m) and m != self.MAIN_FILE]

    @property
    def code(self):
        if self.file_path is None:
            return ""
        return self.get_code(self.file_path)

    @property
    def info(self):
        try:
            data = json.loads(self.notes)
        except Exception:
            data = {}

        def guess_error(notes):
            notes = notes.replace('\\n',' ')
            for er in ['Error', 'Exception', 'error']:
                if er in notes:
                    return re.findall(r'(\w*%s\w*)' % er, notes)[-1] # return the last one

        additional_error = guess_error(self.notes) if self.notes is not None else None

        if 'error' in data:
            return make_space(data['error'].get('type', additional_error or "Error"))

        return str(int_or_flot(self.point) if self.point is not None else "N/A") + \
               (f" ({make_space(additional_error)})" if additional_error is not None else "")

    @property
    def queue(self):
        return Submission.objects.filter(status=Submission.STATUS_QUEUED, created_at__lte=self.created_at).count()

    @property
    def is_late(self):
        if self.task.deadline:
            return self.created_at > self.task.deadline
        return False

    @property
    def suggestions(self):
        if self.notes is None:
            return None
        texts = []
        suggestions = list(Suggestion.objects.filter(course__isnull=True, task__isnull=True).all()) + \
                      list(self.task.suggestions.all()) + list(self.task.course.suggestions.all())
        for suggestion in suggestions:
            matches = re.findall(rf'{suggestion.pattern}', self.notes)
            if matches:
                texts.append(suggestion.text)
        return texts

    def __str__(self):
        return "{}:{} - {} - {} AY{} Sem{}".format(self.user, self.pk, self.task.name,
            self.task.course.code, self.task.course.academic_year, self.task.course.semester)
