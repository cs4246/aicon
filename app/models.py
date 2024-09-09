from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import reverse
from django.core.files.storage import default_storage
import os
import hashlib
import json
import re
import secrets

class ExtraFileField(models.FileField):
    def __init__(self, verbose_name=None, name=None, upload_to='', after_file_save=None, storage=None, **kwargs):
        self.after_file_save = after_file_save
        super().__init__(verbose_name, name, upload_to=upload_to, storage=storage or default_storage, **kwargs)

    def pre_save(self, model_instance, add):
        file = super().pre_save(model_instance, add)
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

def make_safe_filename(s):
    def safe_char(c):
        if c.isalnum():
            return c
        else:
            return "_"
    return "".join(safe_char(c) for c in s).rstrip("_")

def submission_path(instance, filename):
    return 'courses/{}/tasks/{}/submissions/{}/{}'.format(
        instance.task.course.id, make_safe_filename(instance.task.name), instance.user.id, filename
    )

def task_path(instance, filename):
    return 'courses/{}/tasks/{}/{}'.format(
        instance.course.id, make_safe_filename(instance.name), filename
    )

def compute_file_hash(instance):
    with instance.file.open():
        instance.file_hash = hash_file(instance.file)


class Course(models.Model):
    class Meta:
        unique_together = (('code', 'academic_year', 'semester'),)

    code = models.CharField(max_length=6)
    academic_year = models.CharField(max_length=30)
    semester = models.PositiveSmallIntegerField()
    visible = models.BooleanField(default=True)
    participants = models.ManyToManyField(
        User,
        through='Participation',
        through_fields=('course', 'user'),
    )

    def __str__(self):
        return "{} - {} Semester {}".format(self.code, self.academic_year, self.semester)

    def __eq__(self, other):
        if not isinstance(other, Course):
            return False
        return self.code == other.code and self.academic_year == other.academic_year and self.semester == other.semester

    def __hash__(self):
        return hash((self.code, self.academic_year, self.semester))


class Participation(models.Model):
    ROLE_ADMIN = 'ADM'
    ROLE_GUEST = 'GUE'
    ROLE_STUDENT = 'STU'
    ROLE_LECTURER = 'LEC'
    ROLE_TEACHING_ASSISTANT = 'TA'
    ROLES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_GUEST, 'Guest'),
        (ROLE_STUDENT, 'Student'),
        (ROLE_LECTURER, 'Lecturer'),
        (ROLE_TEACHING_ASSISTANT, 'Teaching Assistant')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=3,
        choices=ROLES,
        default=ROLE_STUDENT,
    )

    def __str__(self):
        return "{} ({}) - {} AY{} Sem{}".format(self.user.username, self.role, self.course.code, self.course.academic_year, self.course.semester)


class Invitation(models.Model):
    key = models.CharField(primary_key=True, max_length=255, default=secrets.token_urlsafe)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=3,
        choices=Participation.ROLES,
        default=Participation.ROLE_STUDENT,
    )
    valid = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course.code} AY{self.course.academic_year} Sem{self.course.semester} ({self.role}): {self.key}"



class Task(models.Model):
    DEFAULT_MAX_UPLOAD_SIZE = 5 * 1024 # KB
    DEFAULT_DAILY_SUBMISSIONS_LIMIT = 3
    DEFAULT_RUN_TIME_LIMIT = 60 # Second
    DEFAULT_MAX_IMAGE_SIZE = 1000000 # KB

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    file = ExtraFileField(upload_to=task_path, after_file_save=compute_file_hash)
    file_hash = models.CharField(max_length=255)

    template = models.FileField(upload_to=task_path, blank=True, null=True)
    template_file = models.CharField(max_length=255, blank=True, null=True)

    daily_submission_limit = models.PositiveSmallIntegerField(default=DEFAULT_DAILY_SUBMISSIONS_LIMIT)
    max_upload_size = models.IntegerField(default=DEFAULT_MAX_UPLOAD_SIZE)
    run_time_limit = models.IntegerField(default=DEFAULT_RUN_TIME_LIMIT)
    max_image_size = models.IntegerField(default=DEFAULT_MAX_IMAGE_SIZE)

    opened_at = models.DateTimeField(blank=True, null=True)
    deadline_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    leaderboard = models.BooleanField(default=False)

    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='subtasks', null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tasks')

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}".format(self.name)

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

    def __str__(self):
        return "{} - {} AY{} Sem{}".format(self.name, self.course.code, self.course.academic_year, self.course.semester)


class Submission(models.Model):
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

    RUNNER_PYTHON = 'PY'
    RUNNER_DOCKER = 'DO'
    RUNNERS = [
        (RUNNER_PYTHON, 'Python'),
        (RUNNER_DOCKER, 'Docker')
    ]


    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=submission_path, blank=True, null=True)
    docker = models.CharField(max_length=255,blank=True, null=True)

    runner = models.CharField(
        max_length=2,
        choices=RUNNERS,
        default=RUNNER_PYTHON,
    )
    metadata = models.TextField(blank=True, null=True)

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

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else None

    @property
    def file_url(self):
        return reverse('submission_download', args=(self.task.course.pk,self.task.pk, self.pk))

    @property
    def file_size(self):
        try:
            return self.file.size
        except:
            return None

    @property
    def info(self):
        try:
            if self.notes is not None:
                notes = self.notes.replace('\\n',' ')
                for er in ['Error', 'Exception', 'error']:
                     if er in notes:
                        return re.findall(r'(\w*%s\w*)' % er, notes)[-1] # return the last one
            return json.loads(self.notes)['error']['type']
        except:
            return self.point

    @property
    def queue(self):
        return Submission.objects.filter(status=Submission.STATUS_QUEUED, created_at__lte=self.created_at).count()

    @property
    def is_late(self):
        if self.task.deadline:
            return self.created_at > self.task.deadline
        return False

    def __str__(self):
        return "{}:{} - {} - {} AY{} Sem{}".format(self.user, self.pk, self.task.name,
            self.task.course.code, self.task.course.academic_year, self.task.course.semester)


class Similarity(models.Model):
    class Meta:
        unique_together = (('user', 'task', 'submission', 'related'),)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='similarities')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='similarities')
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='similarity')
    related = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='similarities')
    score = models.DecimalField(max_digits=9, decimal_places=3)
    diff = models.TextField(blank=True, null=True)


class Announcement(models.Model):
    TYPE_SUCCESS = 'success'
    TYPE_INFO = 'info'
    TYPE_WARNING = 'warning'
    TYPE_DANGER = 'danger'
    TYPES = [
        (TYPE_SUCCESS, 'Success'),
        (TYPE_INFO, 'Info'),
        (TYPE_WARNING, 'Warning'),
        (TYPE_DANGER, 'Danger')
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=7,
        choices=TYPES,
        default=TYPE_INFO,
    )
    text = models.TextField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return "{} - {} [active={}]".format(self.type, self.name, self.active)
