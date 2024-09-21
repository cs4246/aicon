from django.db import models
from django.contrib.auth.models import User
from app.models.task import Task
from app.models.submission import Submission

class Similarity(models.Model):
    class Meta:
        unique_together = (('user', 'task', 'submission', 'related'),)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='similarities')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='similarities')
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='similarity')
    related = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='similarities')
    score = models.DecimalField(max_digits=9, decimal_places=3)
    diff = models.TextField(blank=True, null=True)
