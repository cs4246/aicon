from django import forms
from app.models import Course, Invitation, Participation
from app.forms.utils import HideableForm, SubmitHelperFormMixin


class CourseForm(SubmitHelperFormMixin, HideableForm):
    class Meta:
        model = Course
        fields = ('code', 'academic_year', 'semester')


class CourseJoinForm(SubmitHelperFormMixin, HideableForm):
    invitation_key = forms.CharField(max_length=255, label="Invitation Key")

    class Meta:
        model = Course
        fields = ('code',)
        widgets = {'code': forms.HiddenInput(),}

    def clean_invitation_key(self):
        invitation_key = self.cleaned_data.get('invitation_key', False)
        try:
            self.invitation = Invitation.objects.get(pk=invitation_key, course=self.instance, valid=True)
            return invitation_key
        except Invitation.DoesNotExist:
            raise forms.ValidationError("Invalid key", code='invalid_key')

    def save(self, commit=True):
        if commit:
            participation = Participation(user=self.user, course=self.instance, role=self.invitation.role)
            participation.save()
        return self.instance
