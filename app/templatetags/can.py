from django import template
from ..utils import can

register = template.Library()

register.simple_tag(can)
