from django.db import models
from django.contrib.auth.models import User
from app.models.course import Course
from app.models.group import Group

class Participation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return "{} ({}) - {} AY{} Sem{}".format(self.user.username, self.group, self.course.code, self.course.academic_year, self.course.semester)
