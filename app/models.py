from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import reverse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from aicon.settings import SUBMISSION_BASE_ZIPFILE, SUBMISSION_BASE_MAIN_DIR, SUBMISSION_BASE_MAIN_FILE, TASK_BASE_MAIN_FILE
from .utils import get_code, make_space, int_or_flot
import os
import hashlib
import json
import re
import secrets
import zipfile

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


class Partition(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


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

    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='subtasks', null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tasks')

    partition = models.ForeignKey(Partition, on_delete=models.CASCADE, null=True, blank=True, related_name="tasks")
    gpus = models.CharField(max_length=255, null=True, blank=True)

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

    def __str__(self):
        return "{} - {} AY{} Sem{}".format(self.name, self.course.code, self.course.academic_year, self.course.semester)


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
        except:
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


class Suggestion(models.Model):
    pattern = models.TextField()
    text = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name="suggestions")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name="suggestions")

    def __str__(self) -> str:
        course_task = [str(x) for x in [self.course, self.task] if x is not None]
        return (f"[{' - '.join(course_task)}]" if len(course_task) > 0 else "[Global]") + " " + f"{self.pattern} -> {self.text}"
