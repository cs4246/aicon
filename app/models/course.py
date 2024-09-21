from django.db import models
from django.contrib.auth.models import User


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

    def role(self, user: User):
        from app.models.participation import Participation # avoid circular import
        try:
            return self.participation_set.get(user=user).get_role_display()
        except Participation.DoesNotExist:
            return None

    def __str__(self):
        return "{} - {} Semester {}".format(self.code, self.academic_year, self.semester)

    def __eq__(self, other):
        if not isinstance(other, Course):
            return False
        return self.code == other.code and self.academic_year == other.academic_year and self.semester == other.semester

    def __hash__(self):
        return hash((self.code, self.academic_year, self.semester))
