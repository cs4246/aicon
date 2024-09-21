from django.views.generic import ListView
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.http.response import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from app.models import Course
from app.forms import CourseJoinForm
from app.views.utils import NeverCacheMixin, AutoSetupMixin, AuthorizationMixin


class CourseMixin(LoginRequiredMixin, NeverCacheMixin, AutoSetupMixin, AuthorizationMixin):
    model = Course
    pk_url_kwarg = "course_pk"


class CourseListView(CourseMixin, ListView):
    queryset = Course.objects.filter(visible=True)
    template_name = "course/list.html"
    context_object_name = "courses"


class CourseJoinView(CourseMixin, UpdateView):
    template_name = "course/join.html"
    form_class = CourseJoinForm
    success_url = reverse_lazy("courses:index")

    def form_valid(self, form):
        form.user = self.request.user # inject user
        form.save()
        return HttpResponseRedirect(self.get_success_url())
