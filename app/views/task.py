from django.http import Http404
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import DeleteView, UpdateView
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from aicon.settings import TASK_BASE_ZIPFILE, SUBMISSION_BASE_ZIPFILE
from app.models import Task
from app.forms import TaskCodeForm, TaskPackageForm
from app.views.utils import AutoSetupMixin, SuccessMessageMixin, NeverCacheMixin, AuthorizationMixin
from app.utils import create_download_response


class TaskMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, AuthorizationMixin):
    model = Task
    pk_url_kwarg = "task_pk"

    def get_success_url(self):
        if "continue" in self.request.POST:
            return reverse("courses:tasks:edit", kwargs={
                "course_pk": self.kwargs["course_pk"],
                "task_pk": self.object.pk,
                "mode": self.kwargs["mode"],
            })
        return reverse("courses:tasks:index", kwargs={"course_pk": self.kwargs["course_pk"]})


class TaskSingleMixin(TaskMixin):
    template_name = "task/edit.html"

    def get_form_class(self):
        match self.kwargs["mode"]:
            case "code":
                return TaskCodeForm
            case "package":
                return TaskPackageForm
            case _:
                raise Http404


class TaskListView(TaskMixin, ListView):
    template_name = "task/list.html"
    context_object_name = "tasks"

    def get_queryset(self):
        return self.course.tasks.all()


class TaskCreateView(TaskSingleMixin, SuccessMessageMixin, UpdateView): # using UpdateView to allow form pre-fill using get_object
    success_message = "Task created: {self.object.name}"

    def get_object(self):
        return Task(course=self.course, file=TASK_BASE_ZIPFILE, template=SUBMISSION_BASE_ZIPFILE)


class TaskUpdateView(TaskSingleMixin, SuccessMessageMixin, UpdateView):
    success_message = "Task saved: {self.object.name}"


class TaskDeleteView(TaskMixin, SuccessMessageMixin, DeleteView):
    success_message = "Task deleted: {self.object.name}"


class TaskDownloadView(TaskMixin, DetailView):
    download_attribute = "file"
    def get(self, request, *args, **kwargs):
        return create_download_response(getattr(self.get_object(), self.download_attribute), "application/zip")


class TaskDownloadTemplateView(TaskDownloadView):
    download_attribute = "template"
