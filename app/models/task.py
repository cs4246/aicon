from django.db import models
from django.utils import timezone
from django.shortcuts import reverse
from aicon.settings import SUBMISSION_BASE_MAIN_FILE, TASK_BASE_MAIN_FILE, TASK_BASE_SETUP_FILE
from app.models.utils import ExtraFileField, compute_file_hash, get_code
from app.models.course import Course
from app.models.partition import Partition
from app.utils import make_safe_filename

import os
import zipfile
import re


def task_path(instance, filename):
    return 'courses/{}/tasks/{}/{}'.format(
        instance.course.id, make_safe_filename(instance.name), filename
    )


class Task(models.Model):
    DEFAULT_MAX_UPLOAD_SIZE = 5 * 1024 # KB
    DEFAULT_DAILY_SUBMISSIONS_LIMIT = 3
    DEFAULT_RUN_TIME_LIMIT = 60 # Second
    DEFAULT_MEMORY_LIMIT = 1048576 # KB
    DEFAULT_MAX_IMAGE_SIZE = 1048576 # KB

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    file = ExtraFileField(upload_to=task_path, after_file_save=compute_file_hash)
    file_hash = models.CharField(max_length=255)

    template = models.FileField(upload_to=task_path, blank=True, null=True)

    daily_submission_limit = models.PositiveSmallIntegerField(default=DEFAULT_DAILY_SUBMISSIONS_LIMIT)
    max_upload_size = models.IntegerField(default=DEFAULT_MAX_UPLOAD_SIZE)
    run_time_limit = models.IntegerField(default=DEFAULT_RUN_TIME_LIMIT)
    memory_limit = models.IntegerField(default=DEFAULT_MEMORY_LIMIT)

    opened_at = models.DateTimeField(blank=True, null=True)
    deadline_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    leaderboard = models.BooleanField(default=False)
    allow_files = models.BooleanField(default=True)

    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='subtasks', null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tasks')

    partition = models.ForeignKey(Partition, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    gpus = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def deadline(self):
        if self.deadline_at:
            return self.deadline_at
        return self.closed_at

    @property
    def is_open(self):
        if self.opened_at and self.opened_at > timezone.now():
            return False
        if self.is_dead:
            return False
        return True

    @property
    def is_late(self):
        return self.deadline_at and self.deadline_at < timezone.now()

    @property
    def is_dead(self):
        return self.closed_at and self.closed_at < timezone.now()

    def get_status_display(self):
        if self.is_dead:
            return "Closed"
        if self.is_late:
            return "Ended"
        return "Open" if self.is_open else "Scheduled"

    @property
    def file_url(self):
        return reverse('task_download', args=(self.course.pk,self.pk))

    @property
    def file_path(self):
        if not self.file or not os.path.exists(self.file.path):
            return None
        try:
            with zipfile.ZipFile(self.file.path, "r", zipfile.ZIP_DEFLATED) as zipf:
                zipf.read(TASK_BASE_MAIN_FILE)
            return self.file.path
        except (zipfile.BadZipFile, KeyError):
            return None

    @property
    def file_content_names(self):
        if self.file_path is None:
            return []
        with zipfile.ZipFile(self.file.path, "r", zipfile.ZIP_DEFLATED) as zipf:
            return zipf.namelist()

    @property
    def file_contents(self):
        return [m for m in self.file_content_names if re.match(r".+\/.+", m) and m != TASK_BASE_MAIN_FILE]

    @property
    def code(self):
        if self.file_path is None:
            return ""
        return get_code(self.file_path, TASK_BASE_MAIN_FILE)

    @property
    def setup(self):
        if self.file_path is None:
            return ""
        return get_code(self.file_path, TASK_BASE_SETUP_FILE)

    @property
    def template_file_path(self):
        if not self.template or not os.path.exists(self.template.path):
            return None
        try:
            with zipfile.ZipFile(self.template.path, "r", zipfile.ZIP_DEFLATED) as zipf:
                zipf.read(SUBMISSION_BASE_MAIN_FILE)
            return self.template.path
        except (zipfile.BadZipFile, KeyError):
            return None

    @property
    def template_file_content_names(self):
        if self.template_file_path is None:
            return []
        with zipfile.ZipFile(self.template.path, "r", zipfile.ZIP_DEFLATED) as zipf:
            return zipf.namelist()

    @property
    def template_file_contents(self):
        return [m for m in self.template_file_content_names if re.match(r".+\/.+", m) and m != SUBMISSION_BASE_MAIN_FILE]

    @property
    def template_code(self):
        if self.template_file_path is None:
            return ""
        return get_code(self.template_file_path, SUBMISSION_BASE_MAIN_FILE)

    @property
    def partition_name(self):
        if self.partition is None:
            return None
        return self.partition.name

    def latest_submission(self, user):
        submissions = self.submissions.filter(user=user)
        if not submissions:
            return None
        return submissions.latest("created_at")

    def submissions_by_user(self, user):
        return self.submissions.filter(user=user).filter(created_at__gt=timezone.localtime(timezone.now()).date())

    def submissions_count_by_user(self, user):
        return self.submissions_by_user(user).count()

    def submissions_exceeded_by_user(self, user):
        return self.daily_submission_limit and self.submissions_count_by_user(user) >= self.daily_submission_limit

    def __str__(self):
        return "{} - {} AY{} Sem{}".format(self.name, self.course.code, self.course.academic_year, self.course.semester)
