
#!/bin/sh

set -e

echo "Starting Myra backend..."

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."

python - <<'PY'
import os
import time
import psycopg

host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
user = os.environ["POSTGRES_USER"]
password = os.environ["POSTGRES_PASSWORD"]
database = os.environ["POSTGRES_DB"]

for attempt in range(30):
    try:
        connection = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database,
            connect_timeout=3,
        )
        connection.close()
        print("PostgreSQL is ready.")
        break
    except Exception as exc:
        print(f"PostgreSQL not ready ({attempt + 1}/30): {exc}")
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL connection failed.")
PY

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec "$@"
