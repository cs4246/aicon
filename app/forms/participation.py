from django import forms
from app.models import Participation
from app.forms.utils import SubmitHelperFormMixin, DisabledFieldsFormMixin


class ParticipationCreateForm(SubmitHelperFormMixin, forms.ModelForm):
    class Meta:
        model = Participation
        fields = ('user', 'group')


class ParticipationUpdateForm(DisabledFieldsFormMixin, ParticipationCreateForm):
    disabled_fields = ['user']
