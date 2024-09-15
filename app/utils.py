import math
import os
import re
from django.http import HttpResponse

def percentile(N, percent, key=lambda x:x):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    """
    if not N:
        return None
    k = (len(N)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c-k)
    d1 = key(N[int(c)]) * (k-f)
    return d0+d1

def quantiles(N, percents):
    N = sorted(N)
    return [percentile(N, p) for p in percents]

def create_download_response(file, content_type):
    filename = os.path.basename(file.name)
    response = HttpResponse(file, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response

def make_space(text):
    return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', text)

def int_or_flot(x):
    return int(float(x)) if int(float(x)) == float(x) else float(x)
