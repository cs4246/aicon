from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from .models import Participation

import os


def create_download_response(file, content_type):
    filename = os.path.basename(file.name)
    response = HttpResponse(file, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def can(course, user, action, submission=None, _self=False):
    try:
        participation = Participation.objects.get(user=user, course=course)
    except Participation.DoesNotExist:
        return "GUE" in settings.ROLES[action]
    permission_self = False
    action_self = f"{action}.self"
    if submission is not None and submission.user == user or _self:
        permission_self = participation.role in settings.ROLES.get(action_self, [])
    permission_general = participation.role in settings.ROLES.get(action, [])
    return permission_self or permission_general
