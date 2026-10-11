web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py seed_data && gunicorn dealerdesk.wsgi:application --bind 0.0.0.0:$PORT
