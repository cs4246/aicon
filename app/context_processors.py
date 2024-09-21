from app.models import Announcement


def get_announcements():
    announcements = Announcement.objects.all()
    for announcement in announcements:
        if not announcement.active:
            continue
        yield (announcement.text, 'alert-' + announcement.type)


def announcements(request):
    return { 'announcements': get_announcements() }
