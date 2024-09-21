from app.models import Invitation
from app.forms.utils import HideableForm

class InvitationForm(HideableForm):
    class Meta:
        model = Invitation
        fields = ('key',)
