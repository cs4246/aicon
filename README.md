# aiVLE: AI Virtual Learning Environment

A platform for lecturers to provide students with an environment to run and grade their artificial intelligence agents.

## Screenshots

| ![Courses](/assets/courses.png?raw=true "Courses") | ![Tasks](/assets/tasks.png?raw=true "Tasks") |
|:-------------------------:|:-------------------------:|
| ![Task Edit](/assets/task_edit.png?raw=true "Task Edit") | ![Submissions](/assets/submissions.png?raw=true "Submissions")
| ![Submission](/assets/submission.png?raw=true "Submission") | ![Leaderboard](/assets/leaderboard.png?raw=true "Leaderboard") |

## Status

This project is still under development, please report any issues if you encounter them.

## Requirements

 * Python > 3.6
 * Django
 * Additional requirements listed in `requirements.txt`

## Setup

Install the requirements
```
pip install -r requirements.txt
```

Create your secret key and store it in ``.env`` as ``SECRET_KEY=<Your Key>``.

Migrate and create the superuser
```
python manage.py makemigrations
python manage.py sqlmigrate app 0001
python manage.py migrate
python manage.py createsuperuser
```

Run server
```
python manage.py runserver
```

## API

Set of API for the runner
```
/api/v1/jobs/			[GET]
/api/v1/jobs/1/			[GET]
/api/v1/jobs/1/run/		[POST]
/api/v1/jobs/1/end/		[POST]
```
