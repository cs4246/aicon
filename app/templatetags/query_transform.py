from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def query_transform(request, **kwargs):
    updated = request.GET.dict()
    updated.update(kwargs)
    return urlencode(updated)
