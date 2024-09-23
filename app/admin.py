from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Course, Invitation, Task, Submission, Participation, Similarity, Announcement, Suggestion, Partition


@admin.register(Course, Task, Submission, Invitation, Participation, Partition, Announcement, Suggestion, Similarity)
class UniversalAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        return [field.name for field in self.model._meta.concrete_fields]


admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UniversalAdmin, UserAdmin):
    actions = [
        'activate_users',
        'deactivate_users',
    ]

    def activate_users(self, request, queryset):
        cnt = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, 'Activated {} users.'.format(cnt))

    def deactivate_users(self, request, queryset):
        cnt = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, 'Deactivated {} users.'.format(cnt))

    activate_users.short_description = 'Activate Users'  # type: ignore
    deactivate_users.short_description = 'Deactivate Users'  # type: ignore
