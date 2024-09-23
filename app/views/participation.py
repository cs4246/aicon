from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, reverse
from django.contrib import messages
from app.models import Participation
from app.forms import ParticipationCreateForm, ParticipationUpdateForm
from app.views.utils import NeverCacheMixin, AutoSetupMixin, CoursePermissionMixin, AutoPermissionRequiredMixin, SuccessMessageMixin


class ParticipationMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, CoursePermissionMixin, AutoPermissionRequiredMixin):
    model = Participation
    pk_url_kwarg = "participation_pk"

    def get_success_url(self):
        return reverse_lazy("courses:participations:index", kwargs={"course_pk": self.kwargs["course_pk"]})


class ParticipationSingleMixin(ParticipationMixin):
    template_name = "participation/edit.html"

    def form_valid(self, form):
        form.instance.course = self.course # inject course
        form.save()
        return super().form_valid(form)


class ParticipationListView(ParticipationMixin, ListView):
    template_name = "participation/list.html"
    context_object_name = "participations"

    def queryset(self):
        return self.course.participation_set.order_by("user__first_name")


class ParticipationCreateView(ParticipationSingleMixin, SuccessMessageMixin, CreateView):
    form_class = ParticipationCreateForm
    success_message = "Participation created: {self.object}"


class ParticipationUpdateAllowedMixin:
    def dispatch(self, request, *args, **kwargs):
        redirect_url = reverse("courses:participations:index", kwargs={
            "course_pk": self.kwargs["course_pk"],
        })

        if self.get_object().user == self.request.user:
            messages.error(self.request, 'You cannot update/delete your own participation.')
            return redirect(redirect_url)

        return super().dispatch(request, *args, **kwargs)


class ParticipationUpdateView(ParticipationUpdateAllowedMixin, ParticipationSingleMixin, SuccessMessageMixin, UpdateView):
    form_class = ParticipationUpdateForm
    success_message = "Participation updated: {self.object}"


class ParticipationDeleteView(ParticipationUpdateAllowedMixin, ParticipationMixin, SuccessMessageMixin, DeleteView):
    success_message = "Participation deleted: {self.object}"
