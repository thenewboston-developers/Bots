import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from trading.models import BotConfig, BotRun
from trading.services.bot_service import BotService, RandyBotStrategy

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_bot(self, bot_config_id: int):
    """
    Main Celery task to run a trading bot.

    Args:
        bot_config_id: ID of the BotConfig to run
    """
    try:
        # Get bot configuration
        bot_config = BotConfig.objects.get(id=bot_config_id)

        if bot_config.status != 'active':
            logger.info(f'Bot {bot_config.name} is not active, skipping run')
            return

        logger.info(f'Starting bot run for: {bot_config.name}')

        # Initialize bot service
        bot_service = BotService(bot_config)

        # Create bot run record
        bot_run = bot_service.create_bot_run()

        # Authenticate
        if not bot_service.authenticate():
            bot_service.finalize_bot_run(status='failed', error_msg='Authentication failed')
            return

        # Execute bot strategy based on type
        if bot_config.bot_type == 'randy':
            strategy = RandyBotStrategy(bot_service)
            success = strategy.execute_iteration()
        else:
            logger.error(f'Unknown bot type: {bot_config.bot_type}')
            bot_service.finalize_bot_run(status='failed', error_msg=f'Unknown bot type: {bot_config.bot_type}')
            return

        # Update iteration count
        bot_run.iterations_completed = 1
        bot_run.save()

        # Finalize bot run
        if success:
            bot_service.finalize_bot_run(status='completed')
            logger.info(f'Bot run completed successfully for: {bot_config.name}')
        else:
            bot_service.finalize_bot_run(status='failed', error_msg='Trade execution failed')
            logger.warning(f'Bot run failed for: {bot_config.name}')

    except BotConfig.DoesNotExist:
        logger.error(f'BotConfig with id {bot_config_id} not found')
    except Exception as e:
        logger.error(f'Error running bot {bot_config_id}: {str(e)}')
        if 'bot_service' in locals():
            bot_service.finalize_bot_run(status='failed', error_msg=str(e))
        raise self.retry(exc=e, countdown=60)


@shared_task
def run_all_active_bots():
    """Run all active bots."""
    active_bots = BotConfig.objects.filter(status='active')

    for bot in active_bots:
        run_bot.delay(bot.id)
        logger.info(f'Queued bot run for: {bot.name}')

    return f'Queued {active_bots.count()} bot runs'


@shared_task
def cleanup_old_bot_runs():
    """Clean up old bot runs and trade logs."""
    cutoff_date = timezone.now() - timedelta(days=30)

    # Delete old bot runs (trades will cascade delete)
    deleted_count = BotRun.objects.filter(started_at__lt=cutoff_date).delete()[0]

    logger.info(f'Cleaned up {deleted_count} old bot runs')
    return f'Deleted {deleted_count} old bot runs'


@shared_task
def update_asset_pairs():
    """Update cached asset pairs from the exchange."""
    from trading.services.bot_service import BotService

    # Use a dummy bot config just for API access
    dummy_config = BotConfig(name='System', api_base_url='https://thenewboston.network/api')

    bot_service = BotService(dummy_config)
    asset_pairs = bot_service.fetch_and_update_asset_pairs()

    logger.info(f'Updated {len(asset_pairs)} asset pairs')
    return f'Updated {len(asset_pairs)} asset pairs'


def setup_periodic_tasks():
    """
    Set up periodic tasks for bots.
    This should be called after migrations are complete.
    """
    # Create or get interval schedules
    every_5_minutes, _ = IntervalSchedule.objects.get_or_create(
        every=5,
        period=IntervalSchedule.MINUTES,
    )

    every_hour, _ = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.HOURS,
    )

    every_day, _ = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.DAYS,
    )

    # Create periodic tasks
    PeriodicTask.objects.get_or_create(
        name='Run all active bots',
        task='trading.tasks.run_all_active_bots',
        defaults={
            'interval': every_5_minutes,
            'enabled': True,
        }
    )

    PeriodicTask.objects.get_or_create(
        name='Update asset pairs',
        task='trading.tasks.update_asset_pairs',
        defaults={
            'interval': every_hour,
            'enabled': True,
        }
    )

    PeriodicTask.objects.get_or_create(
        name='Cleanup old bot runs',
        task='trading.tasks.cleanup_old_bot_runs',
        defaults={
            'interval': every_day,
            'enabled': True,
        }
    )

    logger.info('Periodic tasks set up successfully')
