from django.db import models
from django.utils import timezone
from app.models.course import Course
from app.models.participation import Participation

import secrets


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
