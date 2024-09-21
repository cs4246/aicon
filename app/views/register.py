from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.contrib.auth import login
from app.forms import RegisterForm
from app.views.utils import SuccessMessageMixin


class RegisterView(SuccessMessageMixin, FormView):
    form_class = RegisterForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("courses:index")
    success_message = "Registration successful"

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = True
        user.save()
        login(self.request, user)
        return super().form_valid(form)
