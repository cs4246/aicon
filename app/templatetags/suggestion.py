from django import template
from django.utils.safestring import mark_safe
import re

from .autolink import AUTOLINKS, wrap_link

register = template.Library()

SUGGESTIONS = {
    r"FileNotFoundError.+\.pt": 
        'You have to zip everything inside the agent template, including the \
        <a href="https://packaging.python.org/guides/using-manifest-in/" target="_blank">MANIFEST.in</a>.\
        Also, please make sure that you have included the model / checkpoint *.pt file in its appropriate location inside the zip file.\
        If you haven\'t already, use the absolute path relative to the script file whenever possible for consistency.',
    r"TypeError: can't convert CUDA tensor to numpy": 
        'Use <a href="https://pytorch.org/docs/stable/tensors.html#torch.Tensor.cpu" target="_blank">Tensor.cpu()</a>\
        to copy the tensor to host memory first before converting to Numpy.',
    r"fast-downward.py: not found|fast-downward.py: Permission denied": 
        'Please make sure to follow the submission guideline regarding the path to the Fast Downward.\
        For the Mini Project sample agent, the path is given in the <b>initialize</b> function.',
    r"pyenv: command not found": 
        "The runner failed unexpectedly. Please contact the teaching staff to get the submission regraded.",
    r'{"error": {"type": "RunnerError", "args": \[""\]}}':
        "Please make sure that you are aware of our system <a href='https://github.com/cs4246/meta/wiki/Known-Issues' target='_blank'>known issues</a>.",
    r'deterministic.+1\.|deterministic.+2\.|deterministic.+3\.|deterministic.+4\.|deterministic.+5\.|deterministic.+6\.|deterministic.+7\.': 
        "Please check that your loss function is correct. Make sure that you incorporate `dones` as it is required to correctly compute\
        the Q function for the terminal states, since Q(s,a) = R(s,a) for a terminal state s and any arbitrary action a."
}

@register.filter(is_safe=True)
def suggestion(value):
    if value is None:
        return None
    for k, v in SUGGESTIONS.items():
        matches = re.findall(k, value)
        if matches:
            return mark_safe(v)
    for k, v in AUTOLINKS.items():
        if k in value:
            return mark_safe('Please refer to {}.'.format(wrap_link(k, v)))
    if re.findall(r"Error|error", value):
        return 'Please read the error message carefully and fix accordingly.'
    return None