from django.http import HttpResponse
from django.db.models.aggregates import Max
from django.views.generic.detail import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from app.models import Task
from app.utils import can
from app.views.utils import AutoSetupMixin, AuthorizationMixin

import math
import statistics
import xlwt


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


class LeaderboardView(AutoSetupMixin, LoginRequiredMixin, AuthorizationMixin, DetailView):
    model = Task
    context_object_name = "task"
    pk_url_kwarg = "task_pk"
    template_name = "info/leaderboard.html"

    def get_leaderboard(self):
        user_maxpoints = self.object.submissions.values('user') \
                                    .annotate(max_point=Max('point')) \
                                    .order_by('-max_point') \
                                    .values('max_point')

        submissions = self.object.submissions.order_by('-point').filter(point__in=user_maxpoints)

        # Hack: otherwise will output multiple same user if got the same point on multiple submissions
        leaderboard_list, users = [], {}
        for submission in submissions.all():
            if can(self.object.course, submission.user, 'task.update'):# or not s.user.is_active:
                continue
            if submission.user.id not in users:
                users[submission.user.id] = True
                leaderboard_list.append(submission)

        return leaderboard_list

    def get_stats(self, leaderboard_list):
        if len(leaderboard_list) == 0:
            return {}

        points = [float(s.point) for s in leaderboard_list]
        max_point = int(max(points))
        partition = max_point # 4
        step_size = int(max_point/partition)
        labels = [i*step_size for i in range(partition+1)]
        distribution = [0 for _ in range(partition+1)]
        for s in leaderboard_list:
            p = math.floor(float(s.point)/float(step_size))
            distribution[p] += 1

        distribution = [round(x_i / len(leaderboard_list) * 100, 2) for x_i in distribution]

        return {
            'labels': labels, 'distribution': distribution,
            'mean': round(statistics.mean(points) ,2), 'median': round(statistics.median(points), 2),
            'quantiles': [round(x, 2) for x in quantiles(points, percents=[0.25, 0.75])]
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leaderboard_list = self.get_leaderboard()
        stats = self.get_stats(leaderboard_list)

        student_view = 'student_view' in self.request.GET
        if not can(self.object.course, self.request.user, 'task.update') or student_view:
            n_show = max(int(len(leaderboard_list) * 0.5), 20)
            leaderboard_list = leaderboard_list[:n_show] # show only half the submissions

        context["submissions"] = leaderboard_list
        context["stats"] = stats
        return context

    def get_self(self):
        return self.task.leaderboard


class LeaderboardDownloadView(LeaderboardView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="{}.xls"'.format(self.object.name)

        wb = xlwt.Workbook(encoding='utf-8')
        sheet = wb.add_sheet('Sheet1')

        font_style = xlwt.XFStyle()
        font_style.font.bold = True
        for i, h in enumerate(['STUDENT_NUMBER', 'MARKS', 'MODERATION', 'REMARKS']):
            sheet.write(0, i, h, font_style)
        for i, s in enumerate(self.get_leaderboard()):
            sheet.write(i+1, 0, s.user.username)
            sheet.write(i+1, 1, s.point)
            sheet.write(i+1, 2, '')
            sheet.write(i+1, 3, 'Late submission' if s.is_late else '')

        wb.save(response)
        return response
