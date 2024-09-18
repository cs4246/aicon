from tempfile import template
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models.aggregates import Max
from django.http import HttpResponse
from django.contrib.auth import login, authenticate
from django.core.paginator import Paginator
from django.db.models import Count
from django.views.decorators.cache import cache_control
from aicon.settings import SUBMISSION_BASE_MAIN_FILE, SUBMISSION_BASE_ZIPFILE, TASK_BASE_ZIPFILE, TASK_BASE_MAIN_FILE

from .models import Course, Invitation, Task, Submission, Participation
from .forms import TaskForm, TaskCodeForm, SubmissionForm, SubmissionCodeForm, CourseForm, RegisterForm, CourseJoinForm
from .funcs import can, submission_evaluate, submission_is_allowed, course_participations, course_participation
from . import utils

import re
import os
import xlwt
import collections
import math
import statistics

from django.http import HttpResponse
from datetime import date, timedelta


@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def courses(request):
    return render(request, 'courses.html', {'course_participations': course_participations(request.user, with_form=True)})

@login_required
def course_join(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    form = CourseJoinForm(request.POST or None)

    if request.POST and form.is_valid():
        try:
            invitation = Invitation.objects.get(pk=form.cleaned_data['invitation_key'], course=course, valid=True)
        except Invitation.DoesNotExist:
            messages.error(request, 'Invalid invitation key')
            return redirect(reverse('course_join', args=(course_pk,)))

        redirect_url = reverse('courses')
        cp = course_participation(request.user, course)

        if cp.joined:
            messages.error(request, 'You have already joined the course.')
            return redirect(redirect_url)

        if not can(course, request.user, 'course.join', participation=cp.participation):
            messages.error(request, 'You can\'t join this course.')
            return redirect(redirect_url)

        participation = Participation(user=request.user, course=course, role=invitation.role)
        participation.save()
        return redirect(redirect_url)

    return render(request, 'course_join.html', {'form': form, 'course': course})

@login_required
def course_add(request):
    redirect_url = reverse('courses')

    course = Course()
    form = CourseForm(request.POST or None, instance=course)

    if request.POST and form.is_valid():
        cp = course_participation(request.user, form.instance)

        if cp.added:
            messages.error(request, 'The course is already added.')
            return redirect(redirect_url)

        if not can(course, request.user, 'course.add', participation=cp.participation):
            messages.error(request, 'You are not allowed to add course.')
            return redirect(redirect_url)

        form.save()

        participation = Participation(user=request.user, course=course, role=cp.participation.role)
        participation.save()

    return redirect(redirect_url)

@login_required
def course_delete(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)

    cp = course_participation(request.user, course)

    if not can(course, request.user, 'course.delete', participation=cp.participation):
        messages.error(request, 'You can\'t delete this course.')
    else:
        course.delete()

    return redirect(reverse('courses'))

@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def course(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)

    if not can(course, request.user, 'course.view'):
        messages.error(request, 'You are not participating in this course.')
        return redirect(reverse('courses'))

    return render(request, 'course.html', {'course': course})

@login_required
def _task_edit(request, course_pk, form_class, task_pk=None):
    course = get_object_or_404(Course, pk=course_pk)

    if not can(course, request.user, 'task.edit'):
        messages.error(request, 'You are not allowed to {} task.'.format('edit' if task_pk else 'add'))
        return redirect(reverse('course', args=(course_pk,)))

    if task_pk:
        task = get_object_or_404(Task, pk=task_pk)
    else:
        task = Task(course=course, file=TASK_BASE_ZIPFILE, template=SUBMISSION_BASE_ZIPFILE)

    form = form_class(request.POST or None, request.FILES or None, instance=task)
    if request.POST and form.is_valid():
        form.save()

        redirect_url = reverse('course', args=(course_pk,))
        return redirect(redirect_url)

    return render(request, 'task_edit.html', {'form': form})

@login_required
def task_edit_package(request, course_pk, task_pk=None):
    return _task_edit(request, course_pk, form_class=TaskForm, task_pk=task_pk)

@login_required
def task_edit_code(request, course_pk, task_pk=None):
    return _task_edit(request, course_pk, form_class=TaskCodeForm, task_pk=task_pk)

@login_required
def task_delete(request, course_pk, task_pk):
    task = get_object_or_404(Task, pk=task_pk)

    if not can(task.course, request.user, 'task.delete'):
        messages.error(request, 'You are not allowed to delete this task.')
    else:
        task.delete()

    redirect_url = reverse('course', args=(course_pk,))
    return redirect(redirect_url)

@login_required
def task_download(request, pk):
    task = get_object_or_404(Task, pk=pk)
    redirect_url = reverse('course', args=(task.course.pk,))

    if not can(task.course, request.user, 'task.download'):
        messages.error(request, 'You are not allowed to download this task.')
        return redirect(redirect_url)

    filename = os.path.basename(task.file.name)
    response = HttpResponse(task.file, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    return response

@login_required
def template_download(request, pk):
    task = get_object_or_404(Task, pk=pk)
    redirect_url = reverse('course', args=(task.course.pk,))

    if not can(task.course, request.user, 'task.view'):
        messages.error(request, 'You are not allowed to download this template.')
        return redirect(redirect_url)

    filename = os.path.basename(task.template.name)
    response = HttpResponse(task.template, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    return response

def _submissions(request, course_pk, task_pk, template='submissions.html', status=None):
    task = get_object_or_404(Task, pk=task_pk)
    redirect_url = reverse('course', args=(task.course.pk,))

    if not can(task.course, request.user, 'task.view'):
        messages.error(request, 'You are not allowed to view this task.')
        return redirect(redirect_url)

    view_all = 'others' in request.GET
    if view_all:
        if not can(task.course, request.user, 'submission.view'):
            messages.error(request, 'You are not allowed to view this task submissions.')
            return redirect(redirect_url)
        submissions = task.submissions.order_by('-created_at')
    else:
        submissions = task.submissions.filter(user=request.user).order_by('-created_at')
    submissions = submissions.all()

    per_page_options = [10, 20, 50, 100, 1000]
    per_page = request.GET.get('per_page', 10)
    paginator = Paginator(submissions, per_page) # Show 25 contacts per page
    page = request.GET.get('page')
    submissions = paginator.get_page(page)

    return render(request, template, {'task': task, 'submissions': submissions, 'view_all': view_all,
                                                'per_page_options': per_page_options}, status=status)

@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def submissions(request, course_pk, task_pk):
    return _submissions(request, course_pk, task_pk, template='submissions.html')

@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def partial_submissions(request, course_pk, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    status = None
    if task.submissions.filter(status__in=[Submission.STATUS_QUEUED, Submission.STATUS_RUNNING]).count() == 0:
        status = 286
    return _submissions(request, course_pk, task_pk, template='partials/submissions.html', status=status)

@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def leaderboard(request, course_pk, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    redirect_url = reverse('submissions', args=(course_pk,task_pk))

    if not can(task.course, request.user, 'task.view'):
        messages.error(request, 'You are not participating in this course.')
        return redirect(redirect_url)

    if not can(task.course, request.user, 'task.edit') and not task.leaderboard:
        messages.error(request, 'Task doesn\'t have leaderboard.')
        return redirect(redirect_url)


    user_maxpoints = task.submissions.values('user') \
                                .annotate(max_point=Max('point')) \
                                .order_by('-max_point') \
                                .values('max_point')

    submissions = task.submissions.order_by('-point').filter(point__in=user_maxpoints)

    # Hack: otherwise will output multiple same user if got the same point on multiple submissions
    leaderboard_list, users = [], {}
    for s in submissions.all():
        if can(task.course, s.user, 'task.edit'):# or not s.user.is_active:
            continue
        if s.user.id not in users:
            users[s.user.id] = True
            leaderboard_list.append(s)

    if len(leaderboard_list) == 0:
        return render(request, 'leaderboard.html', {'task': task, 'submissions': leaderboard_list, 'stats': {} })

    # Compute distribution
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

    stats = {'labels': labels, 'distribution': distribution,
             'mean': round(statistics.mean(points) ,2), 'median': round(statistics.median(points), 2),
             'quantiles': [round(x, 2) for x in utils.quantiles(points, percents=[0.25, 0.75])] }

    student_view = 'student_view' in request.GET
    if not can(task.course, request.user, 'task.edit') or student_view:
        n_show = max(int(len(leaderboard_list) * 0.5), 20)
        leaderboard_list = leaderboard_list[:n_show] # show only half the submissions

    if 'download' in request.GET:
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="{}.xls"'.format(task.name)

        wb = xlwt.Workbook(encoding='utf-8')
        sheet = wb.add_sheet('Sheet1')

        font_style = xlwt.XFStyle()
        font_style.font.bold = True
        for i, h in enumerate(['STUDENT_NUMBER', 'MARKS', 'MODERATION', 'REMARKS']):
            sheet.write(0, i, h, font_style)
        for i, s in enumerate(leaderboard_list):
            sheet.write(i+1, 0, s.user.username)
            sheet.write(i+1, 1, s.point)
            sheet.write(i+1, 2, '')
            sheet.write(i+1, 3, 'Late submission' if s.is_late else '')

        wb.save(response)
        return response

    return render(request, 'leaderboard.html', {'task': task, 'submissions': leaderboard_list, 'stats': stats})

@login_required
def similarities(request, course_pk, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    redirect_url = reverse('submissions', args=(course_pk,task_pk))

    if not can(task.course, request.user, 'task.edit') and not task.leaderboard:
        messages.error(request, 'You don\'t have access similarities feature.')
        return redirect(redirect_url)

    similarities_ = task.similarities.order_by('-score', 'submission__created_at').all()
    similarities = []
    for s in similarities_.all():
        if can(task.course, s.user, 'task.edit') or not s.user.is_active:
            continue
        similarities.append(s)

    per_page_options = [10, 20, 50, 100, 1000]
    per_page = request.GET.get('per_page', per_page_options[0])
    paginator = Paginator(similarities, per_page) # Show 25 contacts per page
    page = request.GET.get('page')
    similarities = paginator.get_page(page)

    return render(request, 'similarities.html', {'task': task, 'similarities': similarities,
                                                'per_page_options': per_page_options})

@login_required
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def stats(request, course_pk, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    redirect_url = reverse('submissions', args=(course_pk,task_pk))

    if not can(task.course, request.user, 'task.edit'):
        messages.error(request, 'You can\'t see the stats of this task.')
        return redirect(redirect_url)

    base = task.submissions.extra({'created_at':"date(created_at)"}).values('created_at')
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

    if task.opened_at is None or task.closed_at is None:
        messages.error(request, "Task doesn't have opening or closing date.")
        return redirect(redirect_url)

    sdate = task.opened_at.date() #date(*[int(i) for i in labels[0].split('-')])
    edate = task.closed_at.date() # date(*[int(i) for i in labels[-1].split('-')])
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

    return render(request, 'stats.html', {'task': task, 'labels': labels, 'data': data})

@login_required
def _submission_new(request, course_pk, task_pk, form_class, base_submission=None):
    task = get_object_or_404(Task, pk=task_pk)
    redirect_url = reverse('submissions', args=(course_pk,task_pk))

    if not can(task.course, request.user, 'task.submit'):
        messages.error(request, 'You are not allowed to submit this task.')
        return redirect(redirect_url)

    if not can(task.course, request.user, 'task.edit'):
        if not task.is_open:
            messages.error(request, 'Task is {}.'.format(task.get_status_display().lower()))
            return redirect(redirect_url)
        if not submission_is_allowed(task, request.user):
            messages.error(request, 'Daily submission limit exceeded.')
            return redirect(redirect_url)

    if task.is_late:
        messages.warning(request, 'You are doing late submission. Your mark will be deducted according to the late submission policy.')

    submission = Submission(task=task, user=request.user)

    if form_class.__name__ == 'SubmissionCodeForm': # Hack: can't check with isinstance'
        if base_submission is None:
            base_submission = Submission(file=task.template or Submission.TEMPLATE_ZIP_FILE)

        base = {"code": base_submission.code}
        if base_submission.pk is None:
            base["description"] = ""
        elif "FROM" in base_submission.description:
            base["description"] = re.sub(r"\[[A-Z]+ (.+)\]", f"[FROM {str(base_submission.filename)}]", base_submission.description)
        else:
            base["description"] = f"[FROM {base_submission.filename}]"
        form = form_class(request.POST or base, request.FILES or None, instance=submission, base_submission=base_submission)
    else:
        form = form_class(request.POST or None, request.FILES or None, instance=submission)

    if request.POST and form.is_valid():
        form.save()
        submission_evaluate(request, task, submission)

        return redirect(redirect_url)

    return render(request, 'submission_new.html', {'form': form, 'base_submission': base_submission})

@login_required
def submission_new_package(request, course_pk, task_pk):
    return _submission_new(request, course_pk, task_pk, form_class=SubmissionForm)

@login_required
def _submission_new_code(request, course_pk, task_pk, submission=None):
    return _submission_new(request, course_pk, task_pk,
        form_class=SubmissionCodeForm,
        base_submission=submission,
    )

@login_required
def submission_new_code(request, course_pk, task_pk):
    return _submission_new_code(request, course_pk, task_pk)

@login_required
def submission_clone_code(request, course_pk, task_pk, submission_pk):
    submission = get_object_or_404(Submission, pk=submission_pk)
    return _submission_new_code(request, course_pk, task_pk, submission=submission)

@login_required
def submission_download(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    redirect_url = reverse('submissions', args=(submission.task.course.pk,submission.task.pk))

    if not can(submission.task.course, request.user, 'submission.download', submission=submission):
        messages.error(request, 'You are not allowed to download this submission.')
        return redirect(redirect_url)

    filename = os.path.basename(submission.file.name)
    response = HttpResponse(submission.file, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    return response

@login_required
def submissions_action(request):
    if request.method == 'POST':
        if 'rerun' in request.POST:
            return submissions_rerun(request)
    return redirect(request.META.get('HTTP_REFERER'))

@login_required
def submissions_rerun(request):
    if request.method == 'POST':
        pks = [int(pk) for pk in request.POST.getlist('submissions_selected[]')]
        submissions_q = Submission.objects.filter(pk__in=pks)

        # Permission check
        for submission in submissions_q.all():
            if not can(submission.task.course, request.user, 'submission.rerun', submission=submission):
                redirect_url = reverse('submissions', args=(submission.task.course.pk,submission.task.pk))
                messages.error(request, 'You are not allowed to rerun this submission: {}.'.format(submission.pk))
                return redirect(redirect_url)

        submissions_q.update(status=Submission.STATUS_QUEUED)

        for submission in submissions_q.all():
            submission_evaluate(request, submission.task, submission)

        messages.info(request, 'Submissions re-queued for run: {}.'.format(sorted(pks)))

    return redirect(request.META.get('HTTP_REFERER'))

def signup(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.cleaned_data['is_active'] = False
            user = form.save(commit=False)
            user.is_active = True
            user.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            login(request, user)
            messages.info(request, 'Registration successful.')
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'signup.html', {'form': form})
