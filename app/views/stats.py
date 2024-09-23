from django.http import HttpResponse
from django.db.models.aggregates import Max, Count
from django.views.generic.detail import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from app.models import Task, Submission
from app.views.utils import AutoSetupMixin, TaskPermissionMixin, AutoPermissionRequiredMixin
from datetime import timedelta

import collections


class StatsDetailView(AutoSetupMixin, LoginRequiredMixin, TaskPermissionMixin, AutoPermissionRequiredMixin, DetailView):
    model = Task
    context_object_name = "task"
    pk_url_kwarg = "task_pk"
    template_name = "info/stats.html"

    def get_stats(self):
        if self.object.opened_at is None or self.object.closed_at is None:
            return {}

        base = self.object.submissions.extra({'created_at':"date(created_at)"}).values('created_at')
        submissions = base.annotate(count=Count('id')).all()
        successes = base.filter(status=Submission.STATUS_DONE).annotate(count=Count('id')).all()
        failures = base.filter(status=Submission.STATUS_ERROR).annotate(count=Count('id')).all()

        points = []
        max_point = base.aggregate(Max('point'))['point__max'] or 0
        max_point = int(max_point) + 1
        partition = max_point # 4
        step_size = int(max_point/partition)
        for p in range(0, max_point, step_size):
            point = base.filter(point__range=(p, p+step_size-0.001)).annotate(count=Count('user')).all()
            points.append(point)

        labels = [d['created_at'] for d in submissions]
        sdate = self.object.opened_at.date() #date(*[int(i) for i in labels[0].split('-')])
        edate = self.object.closed_at.date() # date(*[int(i) for i in labels[-1].split('-')])
        delta = edate - sdate

        counts = collections.OrderedDict({})
        for i in range(delta.days + 1):
            day = sdate + timedelta(days=i)
            counts[str(day)] = {'successes':0, 'failures':0, 'points': [0] * partition}

        for s in successes:
            if s['created_at'] in counts:
                counts[s['created_at']]['successes'] = s['count']
        for s in failures:
            if s['created_at'] in counts:
                counts[s['created_at']]['failures'] = s['count']
        for p in range(0, max_point, step_size):
            _sum = 0
            for s in points[p]:
                if s['created_at'] in counts:
                    _sum = s['count'] + _sum
                    counts[s['created_at']]['points'][p] = _sum
            for i, day in enumerate(counts.keys()):
                if day in counts and counts[day]['points'][p] < 1:
                    prev_day = list(counts.keys())[i-1]
                    counts[day]['points'][p] = counts[prev_day]['points'][p]

        # TODO: per user points

        labels = []
        data = {'successes': [], 'failures': [], 'points': [[] for i in range(partition)]}
        for day, stat in counts.items():
            labels.append(day)
            data['successes'].append(stat['successes'])
            data['failures'].append(stat['failures'])
            for p in range(0, max_point, step_size):
                data['points'][p].append(stat['points'][p])
        data['successes_count'] = sum(data['successes'])
        data['failures_count'] = sum(data['failures'])

        return {'labels': labels, 'data': data}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stats = self.get_stats()
        context = {**stats, **context}
        return context
