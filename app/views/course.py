from django.views.generic import ListView
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django.urls import reverse_lazy
from django.http.response import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from app.models import Course, Participation, Group
from app.forms import CourseForm, CourseJoinForm
from app.views.utils import NeverCacheMixin, AutoSetupMixin, CoursePermissionMixin, AutoPermissionRequiredMixin, SuccessMessageMixin


class CourseMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, CoursePermissionMixin, AutoPermissionRequiredMixin):
    model = Course
    pk_url_kwarg = "course_pk"
    success_url = reverse_lazy("courses:index")


class CourseSingleMixin(CourseMixin):
    form_class = CourseForm
    template_name = "course/edit.html"


class CourseListView(CourseMixin, ListView):
    queryset = Course.objects.filter(visible=True)
    template_name = "course/list.html"
    context_object_name = "courses"


class CourseCreateView(CourseSingleMixin, SuccessMessageMixin, CreateView):
    success_message = "Course created: {self.object}"

    def form_valid(self, form):
        response = super().form_valid(form)
        participation = Participation(user=self.request.user, course=form.instance, group=Group.objects.get(Group.ADMIN))
        participation.save()
        return response


class CourseUpdateView(CourseSingleMixin, SuccessMessageMixin, UpdateView):
    success_message = "Course saved: {self.object}"


class CourseDeleteView(CourseMixin, SuccessMessageMixin, DeleteView):
    success_message = "Course deleted: {self.object}"


class CourseJoinView(CourseMixin, UpdateView):
    template_name = "course/join.html"
    form_class = CourseJoinForm

    def form_valid(self, form):
        form.user = self.request.user # inject user
        form.save()
        return HttpResponseRedirect(self.get_success_url())
