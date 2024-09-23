from typing import Optional
from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):
    class Meta:
        unique_together = (('code', 'academic_year', 'semester'),)

    code = models.CharField(max_length=32)
    academic_year = models.CharField(max_length=32)
    semester = models.PositiveSmallIntegerField()
    visible = models.BooleanField(default=True)
    participants = models.ManyToManyField(
        User,
        through='Participation',
        through_fields=('course', 'user'),
    )

    @property
    def name(self) -> Optional[str]:
        if self.code is None or self.academic_year is None or self.semester is None:
            return None
        return "{} - {} Semester {}".format(self.code, self.academic_year, self.semester)

    def group(self, user: User) -> Optional[str]:
        from app.models.participation import Participation # avoid circular import
        try:
            return self.participation_set.get(user=user).group
        except Participation.DoesNotExist:
            return None

    def __str__(self):
        return self.name or "None"

    def __eq__(self, other):
        if not isinstance(other, Course):
            return False
        return self.code == other.code and self.academic_year == other.academic_year and self.semester == other.semester

    def __hash__(self):
        return hash((self.code, self.academic_year, self.semester))
