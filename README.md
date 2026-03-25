# AlertStream - Multi-Channel Notification Service

A production-grade SaaS platform for sending notifications across multiple channels including Email, SMS, Push Notifications, Slack, Telegram, WhatsApp, and Webhooks.

## Features

- **Multi-Channel Delivery**: Send notifications via Email, SMS, Push, Slack, Telegram, WhatsApp, and Webhooks
- **Template Engine**: Create and manage notification templates with variable substitution and Jinja2 support
- **Smart Routing**: Configure routing rules with conditions to automatically select delivery channels
- **Delivery Tracking**: Real-time tracking of notification delivery status with detailed logs
- **Retry Logic**: Configurable retry policies with exponential backoff for failed deliveries
- **Rate Limiting**: Per-organization and per-channel rate limiting to prevent abuse
- **Analytics Dashboard**: Comprehensive delivery analytics, failure breakdowns, and channel performance metrics
- **API Key Management**: Secure API key authentication for programmatic access
- **Multi-Tenant**: Full organization-based multi-tenancy with isolated data
- **Real-Time Updates**: WebSocket support for live delivery status updates

## Architecture

```
                    +------------------+
                    |   React Frontend |
                    |   (Port 3000)    |
                    +--------+---------+
                             |
                    +--------v---------+
                    |      Nginx       |
                    |   (Port 80/443)  |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Django + DRF    |
                    |  (Port 8000)     |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v----+  +-----v------+  +----v-------+
     |  PostgreSQL  |  |   Redis    |  |   Celery   |
     |  (Port 5432) |  | (Port 6379)|  |  Workers   |
     +--------------+  +------------+  +------------+
```

## Tech Stack

- **Backend**: Django 5.x, Django REST Framework, Channels (WebSocket)
- **Frontend**: React 18, Redux Toolkit, Recharts, React Router v6
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Task Queue**: Celery 5.x with Redis broker
- **Reverse Proxy**: Nginx
- **Containerization**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/alertstream.git
cd alertstream
```

2. Copy the environment file and configure:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Build and start all services:
```bash
docker-compose up --build
```

4. Run database migrations:
```bash
docker-compose exec backend python manage.py migrate
```

5. Create a superuser:
```bash
docker-compose exec backend python manage.py createsuperuser
```

6. Access the application:
- Frontend: http://localhost
- API: http://localhost/api/
- Admin: http://localhost/admin/
- API Docs: http://localhost/api/docs/

## API Usage

### Authentication

All API requests require an API key header:
```
Authorization: Api-Key YOUR_API_KEY
```

### Send a Notification

```bash
curl -X POST http://localhost/api/v1/notifications/ \
  -H "Authorization: Api-Key YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "user@example.com",
    "channels": ["email", "slack"],
    "template_id": "welcome-email",
    "context": {
      "user_name": "John Doe",
      "activation_link": "https://example.com/activate/abc123"
    },
    "priority": "high"
  }'
```

### List Notifications

```bash
curl http://localhost/api/v1/notifications/ \
  -H "Authorization: Api-Key YOUR_API_KEY"
```

### Get Delivery Status

```bash
curl http://localhost/api/v1/notifications/{id}/status/ \
  -H "Authorization: Api-Key YOUR_API_KEY"
```

## Configuration

### Channel Providers

Configure providers in the Django admin or via the API:

| Channel   | Supported Providers          |
|-----------|------------------------------|
| Email     | SMTP, SendGrid, Mailgun, SES |
| SMS       | Twilio, Vonage, MessageBird  |
| Push      | FCM, APNS, OneSignal         |
| Slack     | Slack API (Bot Token)        |
| Telegram  | Telegram Bot API             |
| WhatsApp  | Twilio WhatsApp, Meta API    |
| Webhook   | Custom HTTP endpoints        |

### Routing Rules

Define routing rules to automatically select channels based on conditions:

```json
{
  "name": "High Priority to All",
  "conditions": [
    {"field": "priority", "operator": "eq", "value": "critical"}
  ],
  "channels": ["email", "sms", "push", "slack"],
  "priority": 1
}
```

### Rate Limiting

Configure rate limits per organization:

```json
{
  "organization": "org-uuid",
  "channel": "email",
  "max_requests": 1000,
  "window_seconds": 3600
}
```

## Development

### Running Tests

```bash
docker-compose exec backend python manage.py test
```

### Code Quality

```bash
docker-compose exec backend flake8
docker-compose exec backend black --check .
```

### Database Migrations

```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

## Environment Variables

See `.env.example` for all available configuration options.

## License

MIT License. See LICENSE for details.
