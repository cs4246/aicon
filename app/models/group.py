from django.contrib.auth.models import Group as BaseGroup
from enum import IntEnum, StrEnum
from typing import Optional


class Group(BaseGroup):
    ADMIN = "Admin"
    LECTURER = "Lecturer"
    TEACHING_ASSISTANT = "Teaching Assistant"
    STUDENT = "Student"
    OBSERVER = "Observer"

    class Meta:
        proxy = True


Group.DEFAULT = Group.OBSERVER
