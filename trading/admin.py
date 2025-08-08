from django.contrib import admin
from django.utils.html import format_html

from trading.models import AssetPair, BotConfig, BotRun, TradeLog, TradingPair


@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'bot_type', 'status_badge', 'last_run', 'total_runs', 'created_at']
    list_filter = ['status', 'bot_type', 'created_at']
    search_fields = ['name', 'api_username']
    readonly_fields = ['last_run', 'total_runs', 'created_at', 'updated_at']

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'bot_type', 'status']
        }),
        ('API Configuration', {
            'fields': ['api_username', 'api_password', 'api_base_url']
        }),
        ('Trading Configuration', {
            'fields': ['max_spend_per_trade', 'min_balance_required', 'sell_probability']
        }),
        ('Schedule Configuration', {
            'fields': ['interval_seconds', 'max_iterations']
        }),
        ('Tracking', {
            'fields': ['last_run', 'total_runs', 'created_at', 'updated_at']
        }),
    ]

    def status_badge(self, obj):
        colors = {'active': 'green', 'paused': 'orange', 'stopped': 'red'}
        return format_html(
            '<span style="color: {};">{}</span>', colors.get(obj.status, 'black'), obj.get_status_display()
        )

    status_badge.short_description = 'Status'  # type: ignore[attr-defined]

    actions = ['activate_bots', 'pause_bots', 'stop_bots']

    def activate_bots(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f'{queryset.count()} bots activated')

    activate_bots.short_description = 'Activate selected bots'  # type: ignore[attr-defined]

    def pause_bots(self, request, queryset):
        queryset.update(status='paused')
        self.message_user(request, f'{queryset.count()} bots paused')

    pause_bots.short_description = 'Pause selected bots'  # type: ignore[attr-defined]

    def stop_bots(self, request, queryset):
        queryset.update(status='stopped')
        self.message_user(request, f'{queryset.count()} bots stopped')

    stop_bots.short_description = 'Stop selected bots'  # type: ignore[attr-defined]


@admin.register(AssetPair)
class AssetPairAdmin(admin.ModelAdmin):
    list_display = ['pair_id', 'primary_currency_ticker', 'secondary_currency_ticker', 'is_active', 'last_fetched']
    list_filter = ['is_active', 'last_fetched']
    search_fields = [
        'primary_currency_ticker', 'secondary_currency_ticker', 'primary_currency_name', 'secondary_currency_name'
    ]
    readonly_fields = ['last_fetched']


@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
    list_display = ['bot_config', 'asset_pair', 'is_enabled', 'priority']
    list_filter = ['is_enabled', 'bot_config']
    search_fields = [
        'bot_config__name', 'asset_pair__primary_currency_ticker', 'asset_pair__secondary_currency_ticker'
    ]


@admin.register(BotRun)
class BotRunAdmin(admin.ModelAdmin):
    list_display = ['bot_config', 'started_at', 'ended_at', 'status_badge', 'iterations_completed']
    list_filter = ['status', 'bot_config', 'started_at']
    search_fields = ['bot_config__name']
    readonly_fields = ['started_at', 'ended_at', 'iterations_completed']

    def status_badge(self, obj):
        colors = {'running': 'blue', 'completed': 'green', 'failed': 'red', 'cancelled': 'orange'}
        return format_html(
            '<span style="color: {};">{}</span>', colors.get(obj.status, 'black'), obj.get_status_display()
        )

    status_badge.short_description = 'Status'  # type: ignore[attr-defined]


@admin.register(TradeLog)
class TradeLogAdmin(admin.ModelAdmin):
    list_display = ['executed_at', 'bot_run', 'asset_pair', 'side', 'price', 'quantity', 'total_value', 'status_badge']
    list_filter = ['status', 'side', 'executed_at', 'bot_run__bot_config']
    search_fields = ['order_id', 'bot_run__bot_config__name']
    readonly_fields = ['executed_at', 'total_value', 'response_data']

    def status_badge(self, obj):
        colors = {'pending': 'blue', 'executed': 'green', 'cancelled': 'orange', 'failed': 'red'}
        return format_html(
            '<span style="color: {};">{}</span>', colors.get(obj.status, 'black'), obj.get_status_display()
        )

    status_badge.short_description = 'Status'  # type: ignore[attr-defined]
