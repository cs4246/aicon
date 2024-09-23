# aicon: AI Contest Platform

A platform that enables lecturers to create an environment where students can run and evaluate their artificial intelligence agents.

## Screenshots

| ![Courses](/assets/courses.png?raw=true "Courses") | ![Tasks](/assets/tasks.png?raw=true "Tasks") |
|:-------------------------:|:-------------------------:|
| ![Task Edit](/assets/task_edit.png?raw=true "Task Edit") | ![Submissions](/assets/submissions.png?raw=true "Submissions")
| ![Submission](/assets/submission.png?raw=true "Submission") | ![Leaderboard](/assets/leaderboard.png?raw=true "Leaderboard") |

## Status

This project is still under development, please report any issues if you encounter them.

## Requirements

 * Python >= 3.12
 * Django
 * Celery
 * Additional requirements listed in `requirements.txt`

## Database

aicon requires a database server. We recommend using MySQL for this purpose. To run MySQL in a Docker container, use the following command:

```bash
docker run --name aicon-mysql -e MYSQL_ROOT_PASSWORD=<your_password> -e MYSQL_DATABASE=aicon -p 3306:3306 -d mysql
```

Be sure to replace `<your_password>` with a strong, secure password of your choice.

If you prefer to use SQLite instead of MySQL, no additional setup is required.

## Message Broker

aicon relies on Celery, which requires a message broker. We recommend using RabbitMQ for this purpose.

To run RabbitMQ using Docker, you can use the following command:
```bash
docker run -d --hostname aicon-rabbit --name aicon-rabbit \
  -e RABBITMQ_DEFAULT_USER=<your_username> \
  -e RABBITMQ_DEFAULT_PASS=<your_password> \
  -p 15672:15672 \
  -p 5672:5672 \
  rabbitmq:3-management
```

Make sure to replace `<your_username>` and `<your_password>` with secure credentials of your choice.

## Setup

1. Install the requirements
  ```bash
  pip install -r requirements.txt
  ```
2. Duplicate the `example.env` file to create a new `.env` file.
3. Update the values in the `.env` file according to server configuration.
4. Create a secret key and store it in ``.env`` as ``SECRET_KEY=<Your Key>``.
5. Migrate, load data, and create the superuser
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  python manage.py loaddata groups partitions
  python manage.py createsuperuser
  ```
6. Run server
  ```bash
  python manage.py runserver
  ```

## API

```
/api/v1/
```
