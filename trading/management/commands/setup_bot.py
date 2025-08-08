from django.core.management.base import BaseCommand, CommandError

from trading.models import BotConfig


class Command(BaseCommand):
    help = 'Set up a new trading bot configuration'  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Name for the bot')
        parser.add_argument('username', type=str, help='API username for the bot')
        parser.add_argument('password', type=str, help='API password for the bot')
        parser.add_argument(
            '--bot-type',
            type=str,
            default='randy',
            choices=['randy', 'strategic', 'llm'],
            help='Type of bot (default: randy)'
        )
        parser.add_argument(
            '--status',
            type=str,
            default='stopped',
            choices=['active', 'paused', 'stopped'],
            help='Initial status of the bot (default: stopped)'
        )
        parser.add_argument('--max-spend', type=float, default=100, help='Maximum spend per trade (default: 100)')
        parser.add_argument('--min-balance', type=float, default=100, help='Minimum balance required (default: 100)')
        parser.add_argument(
            '--sell-probability', type=float, default=0.25, help='Probability of selling vs buying (default: 0.25)'
        )
        parser.add_argument('--interval', type=int, default=60, help='Seconds between bot runs (default: 60)')

    def handle(self, *args, **options):
        name = options['name']

        # Check if bot already exists
        if BotConfig.objects.filter(name=name).exists():
            raise CommandError(f'Bot with name "{name}" already exists')

        # Create bot configuration
        bot_config = BotConfig.objects.create(
            name=name,
            bot_type=options['bot_type'],
            status=options['status'],
            api_username=options['username'],
            api_password=options['password'],
            max_spend_per_trade=options['max_spend'],
            min_balance_required=options['min_balance'],
            sell_probability=options['sell_probability'],
            interval_seconds=options['interval']
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created bot "{name}" with ID {bot_config.id}'))

        if options['status'] == 'active':
            self.stdout.write(
                self.style.WARNING('Bot is set to active. Make sure Celery is running to execute scheduled tasks.')
            )
