# Django Trading Bot Application

A Django-based trading bot application with Celery integration for automated trading on thenewboston.network exchange.

## Features

- **Multiple Bot Types**: Support for Randy (random), Strategic, and LLM-powered bots
- **Database Configuration**: Store bot configs, API credentials, and trading parameters in database
- **Celery Integration**: Asynchronous task execution with Redis broker
- **Django Admin**: Web interface for managing bots and viewing trade logs
- **Modular Architecture**: Service layer for easy extension and testing
- **Comprehensive Logging**: Track all bot runs and trades

## Installation

1. **Install Redis** (for Celery broker):
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows (WSL)
sudo apt-get install redis-server
```

2. **Set up environment**:
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Required: Add your bot API credentials
```

3. **Run migrations**:
```bash
poetry run python manage.py migrate
```

4. **Create superuser** (for admin access):
```bash
poetry run python manage.py createsuperuser
```

## Usage

### Start Services

1. **Start Redis**:
```bash
redis-server
```

2. **Start Celery Worker** (in a new terminal):
```bash
poetry run celery -A tnb_exchange worker -l info
```

3. **Start Celery Beat** (in another terminal, for scheduled tasks):
```bash
poetry run celery -A tnb_exchange beat -l info
```

4. **Start Django Development Server**:
```bash
poetry run python manage.py runserver
```

### Managing Bots

#### Via Django Admin

1. Navigate to http://localhost:8000/admin
2. Log in with your superuser credentials
3. Go to "Bot configs" to create and manage bots

#### Via Management Commands

**Create a new bot**:
```bash
poetry run python manage.py setup_bot "MyBot" "username" "password" \
  --bot-type randy \
  --status active \
  --max-spend 100 \
  --sell-probability 0.25
```

**Run a bot manually**:
```bash
# Run synchronously (blocking)
poetry run python manage.py run_bot "MyBot" --iterations 5

# Run asynchronously via Celery
poetry run python manage.py run_bot "MyBot" --async --iterations 5
```

### API Endpoints

The application can be extended with REST API endpoints for programmatic access. Currently, management is through Django Admin and management commands.

## Project Structure

```
tnb_exchange/           # Django project settings
├── __init__.py        # Celery app initialization
├── celery.py          # Celery configuration
├── settings.py        # Django settings with Celery config
└── urls.py           

trading/               # Trading app
├── models.py         # Database models (BotConfig, AssetPair, etc.)
├── admin.py          # Django admin configuration
├── tasks.py          # Celery tasks for bot execution
├── services/         # Service layer
│   └── bot_service.py  # Core bot logic and strategies
└── management/       # Django management commands
    └── commands/
        ├── run_bot.py    # Manual bot execution
        └── setup_bot.py  # Bot configuration

logs/                 # Application logs
```

## Models

- **BotConfig**: Bot configuration including API credentials and trading parameters
- **AssetPair**: Cached trading pairs from the exchange
- **TradingPair**: Bot-specific enabled trading pairs
- **BotRun**: Log of bot execution runs
- **TradeLog**: Individual trade records

## Celery Tasks

- `run_bot`: Execute a single bot iteration
- `run_all_active_bots`: Run all bots with status='active'
- `update_asset_pairs`: Refresh cached asset pairs from exchange
- `cleanup_old_bot_runs`: Remove old logs (>30 days)

## Configuration

### Environment Variables

- `DEBUG`: Django debug mode (default: True)
- `SECRET_KEY`: Django secret key
- `CELERY_BROKER_URL`: Redis URL (default: redis://localhost:6379/0)
- `DJANGO_LOG_LEVEL`: Logging level (default: INFO)

### Bot Configuration (per bot in database)

- `bot_type`: Type of trading strategy
- `max_spend_per_trade`: Maximum TNB to spend per trade
- `min_balance_required`: Minimum TNB balance to continue trading
- `sell_probability`: Chance of selling vs buying (0-1)
- `interval_seconds`: Seconds between scheduled runs

## Monitoring

- **Django Admin**: View bot runs, trades, and configurations
- **Logs**: Check `logs/trading_bot.log` for detailed execution logs
- **Celery Flower** (optional): Monitor Celery tasks
  ```bash
  pip install flower
  celery -A tnb_exchange flower
  ```

## Testing

Run tests with:
```bash
poetry run python manage.py test trading
```

## Future Enhancements

- REST API for programmatic bot management
- Web dashboard with real-time trading metrics
- WebSocket support for live updates
- LLM integration for intelligent trading strategies
- Advanced trading strategies (technical indicators, ML models)
- Multi-exchange support
- Risk management features
- Backtesting capabilities

## Security Notes

- Store sensitive credentials in environment variables
- Use Django's built-in encryption for API passwords in production
- Implement rate limiting for API calls
- Regular security audits of dependencies
- Use HTTPS in production