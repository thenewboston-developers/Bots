from django.db import models


class BotConfig(models.Model):
    """Configuration for a trading bot instance."""

    BOT_TYPE_CHOICES = [
        ('randy', 'Randy - Random Trading Bot'),
        ('strategic', 'Strategic Trading Bot'),
        ('llm', 'LLM-Powered Trading Bot'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('stopped', 'Stopped'),
    ]

    def __str__(self):
        return f'{self.name} ({self.bot_type})'

    name = models.CharField(max_length=100, unique=True)
    bot_type = models.CharField(max_length=50, choices=BOT_TYPE_CHOICES, default='randy')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='stopped')

    # API Configuration
    api_username = models.CharField(max_length=100)
    api_password = models.CharField(max_length=255)  # Should be encrypted in production
    api_base_url = models.URLField(default='https://thenewboston.network/api')

    # Trading Configuration
    max_spend_per_trade = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    min_balance_required = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    sell_probability = models.FloatField(default=0.25, help_text='Probability of selling vs buying (0-1)')

    # Schedule Configuration
    interval_seconds = models.IntegerField(default=60, help_text='Seconds between bot runs')
    max_iterations = models.IntegerField(default=0, help_text='Max iterations (0 = infinite)')

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(null=True, blank=True)
    total_runs = models.IntegerField(default=0)

    class Meta:
        db_table = 'bot_configs'
        ordering = ['-created_at']


class AssetPair(models.Model):
    """Cached asset pairs from the exchange."""

    def __str__(self):
        return f'{self.primary_currency_ticker}/{self.secondary_currency_ticker}'

    pair_id = models.IntegerField(unique=True)
    primary_currency_ticker = models.CharField(max_length=10)
    secondary_currency_ticker = models.CharField(max_length=10)
    primary_currency_name = models.CharField(max_length=100)
    secondary_currency_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_pairs'
        ordering = ['primary_currency_ticker', 'secondary_currency_ticker']


class TradingPair(models.Model):
    """Specific trading pairs enabled for a bot."""

    def __str__(self):
        return f'{self.bot_config.name} - {self.asset_pair}'

    bot_config = models.ForeignKey(BotConfig, on_delete=models.CASCADE, related_name='trading_pairs')
    asset_pair = models.ForeignKey(AssetPair, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text='Higher priority pairs are selected first')

    class Meta:
        db_table = 'trading_pairs'
        unique_together = ['bot_config', 'asset_pair']
        ordering = ['-priority']


class BotRun(models.Model):
    """Log of bot execution runs."""

    def __str__(self):
        return f'{self.bot_config.name} - {self.started_at}'

    bot_config = models.ForeignKey(BotConfig, on_delete=models.CASCADE, related_name='runs')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ]
    )
    iterations_completed = models.IntegerField(default=0)
    errors = models.TextField(blank=True)

    class Meta:
        db_table = 'bot_runs'
        ordering = ['-started_at']


class TradeLog(models.Model):
    """Log of individual trades executed by bots."""

    def __str__(self):
        return f'{self.side} {self.quantity} @ {self.price}'

    bot_run = models.ForeignKey(BotRun, on_delete=models.CASCADE, related_name='trades')
    asset_pair = models.ForeignKey(AssetPair, on_delete=models.SET_NULL, null=True)
    side = models.CharField(max_length=4, choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    price = models.DecimalField(max_digits=18, decimal_places=8)
    quantity = models.DecimalField(max_digits=18, decimal_places=8)
    total_value = models.DecimalField(max_digits=18, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    order_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('executed', 'Executed'),
            ('cancelled', 'Cancelled'),
            ('failed', 'Failed'),
        ]
    )
    response_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'trade_logs'
        ordering = ['-executed_at']
