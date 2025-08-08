from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AssetPair, BotConfig, BotRun, TradeLog


class BotConfigModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.bot_config = BotConfig.objects.create(
            name='Test Bot',
            bot_type='randy',
            status='active',
            api_username='testuser',
            api_password='testpass',
            max_spend_per_trade=Decimal('100.00'),
            min_balance_required=Decimal('50.00')
        )

    def test_bot_config_creation(self):
        self.assertEqual(self.bot_config.name, 'Test Bot')
        self.assertEqual(self.bot_config.bot_type, 'randy')
        self.assertEqual(self.bot_config.status, 'active')

    def test_bot_config_str(self):
        self.assertEqual(str(self.bot_config), 'Test Bot (randy)')


class AssetPairModelTest(TestCase):

    def setUp(self):
        self.asset_pair = AssetPair.objects.create(
            pair_id=1,
            primary_currency_ticker='TNB',
            secondary_currency_ticker='BTC',
            primary_currency_name='The New Boston',
            secondary_currency_name='Bitcoin'
        )

    def test_asset_pair_creation(self):
        self.assertEqual(self.asset_pair.primary_currency_ticker, 'TNB')
        self.assertEqual(self.asset_pair.secondary_currency_ticker, 'BTC')

    def test_asset_pair_str(self):
        self.assertEqual(str(self.asset_pair), 'TNB/BTC')


class BotRunModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.bot_config = BotConfig.objects.create(
            name='Test Bot', bot_type='randy', status='active', api_username='testuser', api_password='testpass'
        )
        self.bot_run = BotRun.objects.create(bot_config=self.bot_config, status='completed')

    def test_bot_run_creation(self):
        self.assertEqual(self.bot_run.bot_config, self.bot_config)
        self.assertEqual(self.bot_run.status, 'completed')

    def test_bot_run_str(self):
        self.assertIn('Test Bot', str(self.bot_run))


class TradeLogModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.bot_config = BotConfig.objects.create(
            name='Test Bot', bot_type='randy', status='active', api_username='testuser', api_password='testpass'
        )
        self.asset_pair = AssetPair.objects.create(
            pair_id=1,
            primary_currency_ticker='TNB',
            secondary_currency_ticker='BTC',
            primary_currency_name='The New Boston',
            secondary_currency_name='Bitcoin'
        )
        self.bot_run = BotRun.objects.create(bot_config=self.bot_config, status='completed')
        self.trade_log = TradeLog.objects.create(
            bot_run=self.bot_run,
            asset_pair=self.asset_pair,
            side='BUY',
            price=Decimal('10.00'),
            quantity=Decimal('5.00'),
            total_value=Decimal('50.00'),
            status='executed'
        )

    def test_trade_log_creation(self):
        self.assertEqual(self.trade_log.side, 'BUY')
        self.assertEqual(self.trade_log.price, Decimal('10.00'))
        self.assertEqual(self.trade_log.quantity, Decimal('5.00'))

    def test_trade_log_str(self):
        self.assertIn('BUY', str(self.trade_log))


class ViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.bot_config = BotConfig.objects.create(
            name='Test Bot', bot_type='randy', status='active', api_username='testuser', api_password='testpass'
        )

    def test_dashboard_view_requires_login(self):
        response = self.client.get(reverse('trading:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_bot_list_view_requires_login(self):
        response = self.client.get(reverse('trading:bot_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_bot_detail_view_requires_login(self):
        response = self.client.get(reverse('trading:bot_detail', args=[self.bot_config.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login
