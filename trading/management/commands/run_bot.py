import logging

from django.core.management.base import BaseCommand, CommandError

from trading.models import BotConfig
from trading.services.bot_service import BotService, RandyBotStrategy

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually run a trading bot'  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument('bot_name', type=str, help='Name of the bot to run')
        parser.add_argument('--iterations', type=int, default=1, help='Number of iterations to run (default: 1)')
        parser.add_argument('--async', action='store_true', help='Run the bot asynchronously using Celery')

    def handle(self, *args, **options):
        bot_name = options['bot_name']
        iterations = options['iterations']
        use_async = options['async']

        try:
            bot_config = BotConfig.objects.get(name=bot_name)
        except BotConfig.DoesNotExist:
            raise CommandError(f'Bot "{bot_name}" does not exist')

        if use_async:
            # Run asynchronously using Celery
            from trading.tasks import run_bot

            for i in range(iterations):
                run_bot.delay(bot_config.id)
                self.stdout.write(self.style.SUCCESS(f'Queued bot run {i + 1}/{iterations} for "{bot_name}"'))
        else:
            # Run synchronously
            bot_service = BotService(bot_config)

            for i in range(iterations):
                self.stdout.write(f'Running iteration {i + 1}/{iterations} for "{bot_name}"...')

                # Create bot run record
                bot_run = bot_service.create_bot_run()

                # Authenticate
                if not bot_service.authenticate():
                    bot_service.finalize_bot_run(status='failed', error_msg='Authentication failed')
                    self.stdout.write(self.style.ERROR(f'Authentication failed for "{bot_name}"'))
                    continue

                # Execute bot strategy
                try:
                    if bot_config.bot_type == 'randy':
                        strategy = RandyBotStrategy(bot_service)
                        success = strategy.execute_iteration()
                    else:
                        self.stdout.write(self.style.ERROR(f'Unknown bot type: {bot_config.bot_type}'))
                        bot_service.finalize_bot_run(
                            status='failed', error_msg=f'Unknown bot type: {bot_config.bot_type}'
                        )
                        continue

                    # Update iteration count
                    bot_run.iterations_completed = 1
                    bot_run.save()

                    # Finalize bot run
                    if success:
                        bot_service.finalize_bot_run(status='completed')
                        self.stdout.write(self.style.SUCCESS(f'Iteration {i + 1} completed successfully'))
                    else:
                        bot_service.finalize_bot_run(status='failed', error_msg='Trade execution failed')
                        self.stdout.write(self.style.WARNING(f'Iteration {i + 1} failed'))

                except Exception as e:
                    bot_service.finalize_bot_run(status='failed', error_msg=str(e))
                    self.stdout.write(self.style.ERROR(f'Error in iteration {i + 1}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Finished running bot "{bot_name}"'))
