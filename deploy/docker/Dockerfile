
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/production.txt /app/requirements/production.txt

RUN pip install --upgrade pip \
    && pip install -r requirements/production.txt

# Copy application
COPY . /app/

# Create non-root user
RUN groupadd --system django \
    && useradd --system --gid django --create-home django \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R django:django /app

COPY deploy/docker/entrypoint.sh /entrypoint.sh
COPY deploy/docker/prestop.sh /prestop.sh

RUN chmod +x /entrypoint.sh /prestop.sh

USER django

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--config", "/app/deploy/docker/gunicorn.conf.py"]
