"""aicon URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from app import apis
from app.views import RegisterView, \
                      CourseListView, CourseJoinView, CourseCreateView, CourseUpdateView, CourseDeleteView, \
                      InvitationListView, InvitationCreateView, InvitationUpdateView, InvitationDeleteView, \
                      ParticipationListView, ParticipationCreateView, ParticipationUpdateView, ParticipationDeleteView, \
                      TaskListView, TaskCreateView, TaskUpdateView, TaskDeleteView, TaskDownloadView, TaskDownloadTemplateView, \
                      SubmissionListView, SubmissionCreateView, SubmissionDetailView, SubmissionUpdateView, SubmissionRunView, SubmissionDownloadView, \
                      LeaderboardView, LeaderboardDownloadView, StatsView, SimilarityListView


info_urls = [
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("leaderboard/download/", LeaderboardDownloadView.as_view(), name="leaderboard-download"),
    path("stats/", StatsView.as_view(), name="stats"),
    path("similarities/", SimilarityListView.as_view(), name="similarities"),
]
submissions_urls = [
    path("", SubmissionListView.as_view(), name="index"),
    path("run/", SubmissionRunView.as_view(), name="run"),
    path("add/<str:mode>/", SubmissionCreateView.as_view(), name="create"),
    path("<int:submission_pk>/", SubmissionDetailView.as_view(), name="detail"),
    path("<int:submission_pk>/edit/<str:mode>/", SubmissionUpdateView.as_view(), name="edit"),
    path("<int:submission_pk>/download", SubmissionDownloadView.as_view(), name="download"),
]
participations_urls = [
    path("", ParticipationListView.as_view(), name="index"),
    path("add/", ParticipationCreateView.as_view(), name="create"),
    path("<str:participation_pk>/edit/", ParticipationUpdateView.as_view(), name="edit"),
    path("<str:participation_pk>/delete/", ParticipationDeleteView.as_view(), name="delete"),
]
invitations_urls = [
    path("", InvitationListView.as_view(), name="index"),
    path("add/", InvitationCreateView.as_view(), name="create"),
    path("<str:invitation_pk>/edit/", InvitationUpdateView.as_view(), name="edit"),
    path("<str:invitation_pk>/delete/", InvitationDeleteView.as_view(), name="delete"),
]
tasks_urls = [
    path("", TaskListView.as_view(), name="index"),
    path("add/<str:mode>/", TaskCreateView.as_view(), name="create"),
    path("<int:task_pk>/", RedirectView.as_view(pattern_name='courses:tasks:submissions:index', permanent=False), name="detail"),
    path("<int:task_pk>/edit/<str:mode>", TaskUpdateView.as_view(), name="edit"),
    path("<int:task_pk>/delete/", TaskDeleteView.as_view(), name="delete"),
    path("<int:task_pk>/download/", TaskDownloadView.as_view(), name="download"),
    path("<int:task_pk>/template/download/", TaskDownloadTemplateView.as_view(), name="download-template"),
    path("<int:task_pk>/submissions/", include((submissions_urls, "app"), namespace="submissions")),
    path("<int:task_pk>/info/", include((info_urls, "app"), namespace="info")),
]
courses_urls = [
    path("", CourseListView.as_view(), name="index"),
    path("add", CourseCreateView.as_view(), name="create"),
    path("<int:course_pk>/", RedirectView.as_view(pattern_name='courses:tasks:index', permanent=False), name="detail"),
    path("<int:course_pk>/edit/", CourseUpdateView.as_view(), name="edit"),
    path("<int:course_pk>/delete/", CourseDeleteView.as_view(), name="delete"),
    path("<int:course_pk>/join/", CourseJoinView.as_view(), name="join"),
    path("<int:course_pk>/tasks/", include((tasks_urls, "app"), namespace="tasks")),
    path("<int:course_pk>/invitations/", include((invitations_urls, "app"), namespace="invitations")),
    path("<int:course_pk>/participations/", include((participations_urls, "app"), namespace="participations")),
]
urlpatterns = [
    path('', RedirectView.as_view(pattern_name='courses:index', permanent=False), name='home'),
    path("courses/", include((courses_urls, "app"), namespace="courses")),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', RegisterView.as_view(), name='register'),
    path('api/v1/', include(apis.router.urls)),
]
