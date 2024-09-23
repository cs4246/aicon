from rest_framework.status import HTTP_404_NOT_FOUND
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import viewsets
from rest_framework.routers import DefaultRouter

from .models import Submission, Task, Similarity, User
from .serializers import SubmissionSerializer, TaskSerializer, SimilaritySerializer, SimilaritySubmissionSerializer
from .utils import create_download_response

from itertools import groupby
import json

class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = (IsAdminUser,)

    def list(self, request):
        if request.method == 'GET':
            submissions = Submission.objects.filter(status=Submission.STATUS_QUEUED).order_by('created_at')
            serializer = self.get_serializer(submissions, many=True)
            return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def run(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk, status=Submission.STATUS_QUEUED)
        except Submission.DoesNotExist:
            return Response(status=HTTP_404_NOT_FOUND)

        submission.status = Submission.STATUS_RUNNING
        submission.save()
        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def end(self, request, pk):
        UPDATE_ALLOWED = ['verdict', 'point', 'notes', 'status']
        STATUS_ALLOWED = [Submission.STATUS_DONE, Submission.STATUS_ERROR]

        try:
            submission = Submission.objects.get(pk=pk, status=Submission.STATUS_RUNNING)
        except Submission.DoesNotExist:
            return Response(status=HTTP_404_NOT_FOUND)

        json_data = json.loads(request.body)
        status = json_data.get('status')
        if status and status in STATUS_ALLOWED:
	        for key, value in json_data.items():
	            if key in UPDATE_ALLOWED:
	                setattr(submission, key, value)
	        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

class TaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (IsAdminUser,)

    @action(detail=True, methods=['get'])
    def submissions_by_user(self, request, pk):
        if request.method == 'GET':
            task = Task.objects.get(pk=pk)
            submissions = task.submissions.all()
            key = lambda x: x.user
            grouped_submissions = groupby(sorted(submissions, key=lambda x: x.user.pk), key=key)
            result = {}
            for user, submissions in grouped_submissions:
                if user.has_perm("task.update", task) or not user.is_active:
                    continue
                serializer = SimilaritySubmissionSerializer(submissions, many=True, context={'request': request})
                result[user.pk] = serializer.data
            return Response(result)

    @action(detail=True, methods=['get'])
    def download(self, request, pk):
        task = Task.objects.get(pk=pk)
        return create_download_response(task.file, 'application/zip')

    @action(detail=True, methods=['get'])
    def template_download(self, request, pk):
        task = Task.objects.get(pk=pk)
        return create_download_response(task.template, 'application/zip')


class SimilarityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Similarity.objects.all()
    serializer_class = SimilaritySerializer
    permission_classes = (IsAdminUser,)

    @action(detail=False, methods=['post'])
    def set(self, request):
        UPDATE_ALLOWED = ['score', 'diff']

        json_data = json.loads(request.body)
        try:
            user = User.objects.get(pk=json_data.get('user_id'))
            task = Task.objects.get(pk=int(json_data.get('task_id')))
            submission = Submission.objects.get(pk=json_data.get('submission_id'))
            related = Submission.objects.get(pk=json_data.get('related_id'))
            similarity = Similarity.objects.get(user=user, task=task)
        except (User.DoesNotExist, Task.DoesNotExist):
            return Response(status=HTTP_404_NOT_FOUND)
        except Similarity.DoesNotExist:
            similarity = Similarity(user=user, task=task)

        similarity.submission = submission
        similarity.related = related

        for key in UPDATE_ALLOWED:
            setattr(similarity, key, json_data[key])

        similarity.save()

        serializer = self.get_serializer(similarity)
        return Response(serializer.data)


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = (IsAdminUser,)

    @action(detail=True, methods=['get'])
    def download(self, request, pk):
        submission = Submission.objects.get(pk=pk)
        return create_download_response(submission.file, 'application/zip')


router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='jobs')
router.register(r'tasks', TaskViewSet)
router.register(r'similarities', SimilarityViewSet)
router.register(r'submissions', SubmissionViewSet)
