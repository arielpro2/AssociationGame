cd /root/AssociationGame
python3 -m virtualenv venv
export PYTHONUNBUFFERED=1
export DEBUG=True
export FLASK_SECRETKEY=dev
export POSTGRES_HOST=localhost
export POSTGRES_PASS=arieljan04
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
gunicorn --worker-class eventlet -w 3 app:app
