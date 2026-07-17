release: python manage.py migrate --no-input
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 3
