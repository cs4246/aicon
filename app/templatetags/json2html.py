from django import template
from json2html import json2html as _json2html

register = template.Library()

@register.filter
def json2html(json):
    return _json2html.convert(json=json).replace('<table', '<table class="table table-bordered"').replace('border="1"', '')
