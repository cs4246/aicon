from django.db import models
from app.models.course import Course
from app.models.task import Task

class Suggestion(models.Model):
    pattern = models.TextField()
    text = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name="suggestions")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name="suggestions")

    def __str__(self) -> str:
        course_task = [str(x) for x in [self.course, self.task] if x is not None]
        return (f"[{' - '.join(course_task)}]" if len(course_task) > 0 else "[Global]") + " " + f"{self.pattern} -> {self.text}"
