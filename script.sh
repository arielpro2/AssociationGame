PYTHONUNBUFFERED=1
DEBUG=True
FLASK_SECRETKEY=dev
POSTGRES_HOSTlocalhost
POSTGRES_PASS=arieljan04
POSTGRES_PORT=5432
POSTGRES_USER=postgres
gunicorn --worker-class eventlet -w 3 app:app
