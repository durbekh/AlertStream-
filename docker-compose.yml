version: "3.9"

services:
  db:
    image: postgres:16-alpine
    container_name: alertstream_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-alertstream}
      POSTGRES_USER: ${POSTGRES_USER:-alertstream}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-alertstream_secret}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-alertstream}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: alertstream_redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis_secret}
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-redis_secret}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: alertstream_backend
    restart: unless-stopped
    command: >
      bash -c "python manage.py migrate --noinput &&
               python manage.py collectstatic --noinput &&
               daphne -b 0.0.0.0 -p 8000 config.asgi:application"
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - DATABASE_URL=postgresql://${POSTGRES_USER:-alertstream}:${POSTGRES_PASSWORD:-alertstream_secret}@db:5432/${POSTGRES_DB:-alertstream}
      - REDIS_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/1
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS:-*}
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-http://localhost,http://localhost:3000}
      - DEBUG=${DEBUG:-0}
      - EMAIL_HOST=${EMAIL_HOST:-smtp.gmail.com}
      - EMAIL_PORT=${EMAIL_PORT:-587}
      - EMAIL_HOST_USER=${EMAIL_HOST_USER:-}
      - EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD:-}
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID:-}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN:-}
      - TWILIO_PHONE_NUMBER=${TWILIO_PHONE_NUMBER:-}
      - FCM_SERVER_KEY=${FCM_SERVER_KEY:-}
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN:-}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY:-}
    volumes:
      - ./backend:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: alertstream_celery_worker
    restart: unless-stopped
    command: celery -A config worker -l info -c 4 -Q default,notifications,analytics,retries
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - DATABASE_URL=postgresql://${POSTGRES_USER:-alertstream}:${POSTGRES_PASSWORD:-alertstream_secret}@db:5432/${POSTGRES_DB:-alertstream}
      - REDIS_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/1
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - EMAIL_HOST=${EMAIL_HOST:-smtp.gmail.com}
      - EMAIL_PORT=${EMAIL_PORT:-587}
      - EMAIL_HOST_USER=${EMAIL_HOST_USER:-}
      - EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD:-}
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID:-}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN:-}
      - TWILIO_PHONE_NUMBER=${TWILIO_PHONE_NUMBER:-}
      - FCM_SERVER_KEY=${FCM_SERVER_KEY:-}
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN:-}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY:-}
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: alertstream_celery_beat
    restart: unless-stopped
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - DATABASE_URL=postgresql://${POSTGRES_USER:-alertstream}:${POSTGRES_PASSWORD:-alertstream_secret}@db:5432/${POSTGRES_DB:-alertstream}
      - REDIS_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD:-redis_secret}@redis:6379/1
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: alertstream_frontend
    restart: unless-stopped
    environment:
      - REACT_APP_API_URL=${REACT_APP_API_URL:-http://localhost/api}
      - REACT_APP_WS_URL=${REACT_APP_WS_URL:-ws://localhost/ws}
    ports:
      - "3000:3000"
    depends_on:
      - backend

  nginx:
    image: nginx:1.25-alpine
    container_name: alertstream_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/var/www/static
      - media_volume:/var/www/media
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
