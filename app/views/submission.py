from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.views.generic import ListView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from rest_framework.request import Request
from aicon.celery import app as celery_app
from app.models import Submission, Task
from app.serializers import TaskSerializer, SubmissionSerializer
from app.forms import SubmissionCodeForm, SubmissionPackageForm
from app.views.utils import AutoSetupMixin, SuccessMessageMixin, NeverCacheMixin, StatusResponseMixin, \
                            TaskPermissionMixin, SubmissionPermissionMixin, AutoPermissionRequiredMixin
from app.utils import create_download_response

import re


def submission_evaluate(request: HttpRequest, task: Task, submission: Submission):
    serializer_context = {
        'request': Request(request),
    }
    task_data = TaskSerializer(task, context=serializer_context).data
    submission_data = SubmissionSerializer(submission, context=serializer_context).data
    celery_app.send_task('aicon_runner.tasks.evaluate', args=[task_data, submission_data])


class SubmissionAllowedMixin:
    def dispatch(self, request, *args, **kwargs):
        redirect_url = reverse("courses:tasks:submissions:index", kwargs={
            "course_pk": self.kwargs["course_pk"],
            "task_pk": self.kwargs["task_pk"],
        })

        if self.task.is_late:
            messages.warning(self.request, 'You are doing late submission. Your mark will be deducted according to the late submission policy.')

        # Intercept special permission
        permission_required = self.get_permission_required()[0]
        if request.user.has_perm(permission_required, self.submission if "submission.update" in permission_required else self.task):
            return super().dispatch(request, *args, **kwargs)

        if not self.task.is_open:
            messages.error(self.request, 'Task is {}.'.format(self.task.get_status_display().lower()))
            return redirect(redirect_url)

        if self.task.submissions_exceeded_by_user(self.request.user):
            messages.error(self.request, f'Daily submission limit exceeded: {self.task.daily_submission_limit}')
            return redirect(redirect_url)

        return super().dispatch(request, *args, **kwargs)


class SubmissionMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, StatusResponseMixin, AutoPermissionRequiredMixin):
    model = Submission
    pk_url_kwarg = "submission_pk"


class SubmissionChangeMixin:
    template_name = "submission/edit.html"
    success_message = "Submission created: {self.object.name}"

    def get_permission_required(self):
        permission_required = super().get_permission_required()
        return [f"{perm}.{self.kwargs['mode']}" for perm in permission_required]

    def get_object(self):
        return Submission(task=self.task, user=self.request.user)

    def get_initial(self):
        if "submission_pk" in self.kwargs:
            self.base_submission = get_object_or_404(Submission, pk=self.kwargs["submission_pk"])
        else:
            self.base_submission = Submission(user=self.request.user, task=self.task)

        if self.base_submission.file_path is None:
            self.base_submission.file = self.task.template or Submission.TEMPLATE_ZIP_FILE

        if self.request.POST:
            return self.initial.copy()

        base = {"code": self.base_submission.code}
        if self.base_submission.pk is None:
            base["description"] = ""
        elif "FROM" in self.base_submission.description:
            base["description"] = re.sub(r"\[[A-Z]+ (.+)\]", f"[FROM {str(self.base_submission.name)}]", self.base_submission.description)
        else:
            base["description"] = f"[FROM {self.base_submission.name}] {self.base_submission.description}"
        return base

    def get_form_class(self):
        mode = self.kwargs["mode"]
        if mode not in ["code", "package"]:
            raise Http404
        if mode == "code":
            return SubmissionCodeForm
        else:
            return SubmissionPackageForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.kwargs["mode"] == "package":
            return kwargs
        kwargs.update({"base_submission": self.base_submission})
        kwargs.update({"submission_files_allowed": self.request.user.has_perm("submission.files", self.task)})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_submission"] = self.base_submission
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        submission_evaluate(self.request, self.task, self.object)
        return response

    def get_success_url(self):
        if "continue" in self.request.POST:
            return reverse("courses:tasks:submissions:edit", kwargs={
                "course_pk": self.kwargs["course_pk"],
                "task_pk": self.kwargs["task_pk"],
                "submission_pk": self.object.pk,
                "mode": "code", # can only edit code, not package
            })
        return reverse("courses:tasks:submissions:index", kwargs={
            "course_pk": self.kwargs["course_pk"],
            "task_pk": self.kwargs["task_pk"],
        })


class SubmissionListView(TaskPermissionMixin, SubmissionMixin, ListView):
    template_name = "submission/list.html"
    partial_template_name = "submission/partial/list.html"
    context_object_name = "submissions"
    per_page_options = [10, 20, 50, 100, 1000]

    @property
    def view_all(self):
        return bool(self.request.GET.get("all", 0))

    def get_template_names(self):
        if "partial" in self.request.GET:
            return [self.partial_template_name]
        return super().get_template_names()

    def get_permission_required(self):
        if "all" in self.request.GET:
            return ["submission.list.all"]
        else:
            return ["submission.list"]

    def get_queryset(self):
        submissions = self.task.submissions.order_by('-created_at')
        search = self.request.GET.get("search", None)
        if search is not None:
            submissions = submissions.filter(
                Q(file__icontains=search) |
                Q(description__icontains=search) |
                Q(notes__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__username__icontains=search)
            )
        if self.view_all:
            return submissions
        return submissions.filter(user=self.request.user)

    def get_paginate_by(self, queryset):
        return self.request.GET.get('per_page', 10)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page_options"] = self.per_page_options
        context["view_all"] = self.view_all
        self.object_list = context["object_list"]
        return context

    def get_status(self):
        waiting_submissions = [submission for submission in self.object_list
                               if submission.status in [Submission.STATUS_QUEUED, Submission.STATUS_RUNNING]]
        return 286 if len(waiting_submissions) == 0 else None


class SubmissionCreateView(SubmissionAllowedMixin, TaskPermissionMixin, SubmissionChangeMixin, SubmissionMixin, UpdateView): # using UpdateView to allow form pre-fill using get_object
    pass


class SubmissionUpdateView(SubmissionAllowedMixin, SubmissionPermissionMixin, SubmissionChangeMixin, SubmissionMixin, UpdateView):
    pass


class SubmissionDetailView(SubmissionPermissionMixin, SubmissionMixin, DetailView):
    template_name = "submission/partial/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["single"] = "partial" in self.request.GET
        return context

    def get_status(self):
        return 286 if self.object.status not in [Submission.STATUS_QUEUED, Submission.STATUS_RUNNING] else None


class SubmissionDownloadView(SubmissionPermissionMixin, SubmissionMixin, DetailView):
    def get(self, request, *args, **kwargs):
        return create_download_response(self.get_object().file, "application/zip")


class SubmissionRunView(TaskPermissionMixin, SubmissionMixin, View):
    def post(self, request, *args, **kwargs):
        pks = [int(pk) for pk in request.POST.getlist('submissions_selected[]')]
        submissions_run = Submission.objects.filter(pk__in=pks)

        submissions_run.update(status=Submission.STATUS_QUEUED)

        for submission in submissions_run.all():
            submission_evaluate(request, submission.task, submission)

        messages.info(request, 'Submissions re-queued for run: {}.'.format(sorted(pks)))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
