from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from app.models import Invitation
from app.forms import InvitationCreateForm, InvitationUpdateForm
from app.views.utils import NeverCacheMixin, AutoSetupMixin, AuthorizationMixin, SuccessMessageMixin


class InvitationMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, AuthorizationMixin):
    model = Invitation
    pk_url_kwarg = "invitation_pk"

    def get_success_url(self):
        return reverse_lazy("courses:invitations:index", kwargs={"course_pk": self.kwargs["course_pk"]})


class InvitationSingleMixin(InvitationMixin):
    template_name = "invitation/edit.html"

    def form_valid(self, form):
        form.instance.course = self.course # inject course
        form.save()
        return super().form_valid(form)


class InvitationListView(InvitationMixin, ListView):
    template_name = "invitation/list.html"
    context_object_name = "invitations"

    def queryset(self):
        return self.course.invitation_set.order_by("-created_at")


class InvitationCreateView(InvitationSingleMixin, SuccessMessageMixin, CreateView):
    form_class = InvitationCreateForm
    success_message = "Invitation created: {self.object.key}"


class InvitationUpdateView(InvitationSingleMixin, SuccessMessageMixin, UpdateView):
    form_class = InvitationUpdateForm
    success_message = "Invitation updated: {self.object.key}"


class InvitationDeleteView(InvitationMixin, SuccessMessageMixin, DeleteView):
    success_message = "Invitation deleted"
