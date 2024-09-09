from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Course, Invitation, Task, Submission, Participation, Similarity, Announcement

admin.site.register(Course)
admin.site.register(Task)
admin.site.register(Submission)
admin.site.register(Participation)
admin.site.register(Similarity)
admin.site.register(Announcement)
admin.site.register(Invitation)

admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "date_joined", "is_active")

    actions = [
        'activate_users',
        'deactivate_users',
    ]

    def activate_users(self, request, queryset):
        cnt = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, 'Activated {} users.'.format(cnt))
    activate_users.short_description = 'Activate Users'  # type: ignore

    def deactivate_users(self, request, queryset):
        cnt = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, 'Deactivated {} users.'.format(cnt))
    deactivate_users.short_description = 'Deactivate Users'  # type: ignore
