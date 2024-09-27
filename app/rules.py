from django.contrib.auth.models import User
from app.models import Course, Submission, Group, Invitation, Participation, Task
from typing import Optional, Union, get_args

import rules


def group(user: User, course: Course) -> Optional[Group]:
    try:
        return course.participation_set.get(user=user).group
    except Participation.DoesNotExist:
        return None

def group_name(user: User, course: Course) -> Optional[str]:
    user_group = group(user, course)
    return user_group.name if user_group is not None else None


Transformable = Union[Course,Task,Submission,Invitation,Participation]

class_parent = {
    Submission: "task",
    Task: "course",
    Invitation: "course",
    Participation: "course",
    Course: None,
}

def get_instance(instance: Transformable, target_class: Transformable):
    for current_class, parent in class_parent.items():
        if isinstance(instance, target_class):
            return instance
        if isinstance(instance, current_class):
            instance = getattr(instance, parent)
    raise NotImplementedError(f"Target class {target_class.__name__} is not implemented")

def target_type(target_class, input_class=Transformable):
    def _instance(f):
        def wrapper(*args,  **kwargs):
            args = [get_instance(a, target_class) if isinstance(a, get_args(input_class)) else a for a in args]
            kwargs = {k:(get_instance(v, target_class) if isinstance(v, get_args(input_class)) else v) for k,v in kwargs.items()}
            return f(*args, **kwargs)
        return wrapper
    return _instance


is_admin = rules.is_group_member(Group.ADMIN)
is_lecturer = rules.is_group_member(Group.LECTURER)
is_teaching_assistant = rules.is_group_member(Group.TEACHING_ASSISTANT)
is_student = rules.is_group_member(Group.STUDENT)
is_observer = rules.is_group_member(Group.OBSERVER)


@rules.predicate
@target_type(Course)
def is_course_participant(user: User, course: Course) -> rules.Predicate:
    return course.participation_set.filter(user=user).exists()

@rules.predicate
@target_type(Course)
def is_course_admin(user: User, course: Course) -> rules.Predicate:
    return group_name(user, course) == Group.ADMIN

@rules.predicate
@target_type(Course)
def is_course_lecturer(user: User, course: Course) -> rules.Predicate:
    return group_name(user, course) == Group.LECTURER

@rules.predicate
@target_type(Course)
def is_course_teaching_assistent(user: User, course: Course) -> rules.Predicate:
    return group_name(user, course) == Group.TEACHING_ASSISTANT

@rules.predicate
@target_type(Course)
def is_course_student(user: User, course: Course) -> rules.Predicate:
    return group_name(user, course) == Group.STUDENT

@rules.predicate
@target_type(Course)
def is_course_observer(user: User, course: Course) -> rules.Predicate:
    return group_name(user, course) == Group.OBSERVER

@rules.predicate
@target_type(Submission)
def is_submission_creator(user: User, submission: Submission) -> rules.Predicate:
    return submission.user == user


is_course_manager = is_course_admin | is_course_lecturer
is_course_teaching_staff = is_course_manager | is_course_teaching_assistent


@rules.predicate
@target_type(Task)
def is_task_open(user: User, task: Task) -> rules.Predicate:
    return task.is_open

@rules.predicate
@target_type(Task)
def is_task_published(user: User, task: Task) -> rules.Predicate:
    return task.published

@rules.predicate
@target_type(Task)
def is_task_submission_exceeded(user: User, task: Task) -> rules.Predicate:
    return task.submissions_exceeded_by_user(user)

@rules.predicate
@target_type(Task)
def is_leaderboard_open(user: User, task: Task) -> rules.Predicate:
    return task.leaderboard

@rules.predicate
@target_type(Task)
def is_submission_files_allowed(user: User, task: Task) -> rules.Predicate:
    return task.allow_files


is_task_submittable = is_task_open & is_task_published & ~is_task_submission_exceeded
can_create_submission = is_course_student
can_update_submission = (is_course_student & is_submission_creator)


rules.add_perm("course.list", rules.is_authenticated)
rules.add_perm("course.join", ~is_course_participant)
rules.add_perm("course.detail", is_course_participant)
rules.add_perm("course.create", is_admin | is_lecturer)
rules.add_perm("course.update", is_course_admin)
rules.add_perm("course.delete", is_course_admin)

rules.add_perm("invitation.list", is_course_manager)
rules.add_perm("invitation.detail", is_course_manager)
rules.add_perm("invitation.create", is_course_manager)
rules.add_perm("invitation.update", is_course_manager)
rules.add_perm("invitation.delete", is_course_manager)

rules.add_perm("participation.list", is_course_teaching_staff)
rules.add_perm("participation.detail", is_course_teaching_staff)
rules.add_perm("participation.create", is_course_manager)
rules.add_perm("participation.update", is_course_manager)
rules.add_perm("participation.delete", is_course_manager)

rules.add_perm("task.list", is_course_participant)
rules.add_perm("task.detail", is_course_participant & is_task_published)
rules.add_perm("task.download.template", is_course_participant & is_task_published)
rules.add_perm("task.download", is_course_teaching_staff)
rules.add_perm("task.create", is_course_teaching_staff)
rules.add_perm("task.update", is_course_teaching_staff)
rules.add_perm("task.delete", is_course_manager)

rules.add_perm("submission.list", is_course_participant & is_task_published)
rules.add_perm("submission.list.all", is_course_teaching_staff)
rules.add_perm("submission.detail", is_submission_creator | is_course_teaching_staff)
rules.add_perm("submission.download", is_submission_creator | is_course_teaching_staff)
rules.add_perm("submission.files", is_submission_files_allowed | is_course_teaching_staff)
rules.add_perm("submission.create.permission", can_create_submission | is_course_teaching_staff)
rules.add_perm("submission.update.permission", can_update_submission | is_course_teaching_staff)
rules.add_perm("submission.create.code", (can_create_submission & is_task_submittable) | is_course_teaching_staff)
rules.add_perm("submission.create.package", (can_create_submission & is_task_submittable & is_submission_files_allowed) | is_course_teaching_staff)
rules.add_perm("submission.update.code", (can_update_submission & is_task_submittable) | is_course_teaching_staff)
rules.add_perm("submission.update.package", (can_update_submission & is_task_submittable & is_submission_files_allowed) | is_course_teaching_staff)
rules.add_perm("submission.delete", is_course_manager)
rules.add_perm("submission.run", is_course_teaching_staff)

rules.add_perm("leaderboard.detail", is_leaderboard_open | is_course_teaching_staff)
rules.add_perm("leaderboard.download", is_course_teaching_staff)
rules.add_perm("stats.detail", is_course_teaching_staff)
rules.add_perm("similarity.list", is_course_teaching_staff)
