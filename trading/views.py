from django.shortcuts import get_object_or_404, render

from .models import BotConfig, BotRun, TradeLog


def dashboard(request):
    """Dashboard view showing bot overview."""
    active_bots = BotConfig.objects.filter(status='active').count()
    recent_runs = BotRun.objects.select_related('bot_config').order_by('-started_at')[:5]
    recent_trades = TradeLog.objects.select_related('bot_run__bot_config', 'asset_pair').order_by('-executed_at')[:10]

    context = {
        'active_bots': active_bots,
        'recent_runs': recent_runs,
        'recent_trades': recent_trades,
    }
    return render(request, 'trading/dashboard.html', context)


def bot_list(request):
    """List all bot configurations."""
    bots = BotConfig.objects.all().order_by('-created_at')
    return render(request, 'trading/bot_list.html', {'bots': bots})


def bot_detail(request, bot_id):
    """Detail view for a specific bot."""
    bot = get_object_or_404(BotConfig, id=bot_id)
    recent_runs = bot.runs.order_by('-started_at')[:10]
    recent_trades = TradeLog.objects.filter(bot_run__bot_config=bot).order_by('-executed_at')[:10]

    context = {
        'bot': bot,
        'recent_runs': recent_runs,
        'recent_trades': recent_trades,
    }
    return render(request, 'trading/bot_detail.html', context)


def trade_list(request):
    """List all trades."""
    trades = TradeLog.objects.select_related('bot_run__bot_config', 'asset_pair').order_by('-executed_at')
    return render(request, 'trading/trade_list.html', {'trades': trades})


def run_list(request):
    """List all bot runs."""
    runs = BotRun.objects.select_related('bot_config').order_by('-started_at')
    return render(request, 'trading/run_list.html', {'runs': runs})
