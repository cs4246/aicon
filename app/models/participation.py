from django.db import models
from django.contrib.auth.models import User
from app.models.course import Course

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
