from django.db import models

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
