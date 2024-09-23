from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from app.views.utils import AutoSetupMixin, TaskPermissionMixin, AutoPermissionRequiredMixin


class SimilarityListView(AutoSetupMixin, LoginRequiredMixin, TaskPermissionMixin, AutoPermissionRequiredMixin, ListView):
    template_name = "info/similarities.html"
    context_object_name = "similarities"
    per_page_options = [10, 20, 50, 100, 1000]

    def get_queryset(self):
        return self.task.similarities.order_by('-score', 'submission__created_at')

    def get_paginate_by(self, queryset):
        return self.request.GET.get('per_page', 10)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page_options"] = self.per_page_options
        return context
