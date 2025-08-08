import logging
import random
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from thenewboston.api_client import TNBApiClient
from trading.models import AssetPair, BotConfig, BotRun, TradeLog

logger = logging.getLogger(__name__)


class BotService:
    """Service layer for bot trading operations."""

    def __init__(self, bot_config: BotConfig):
        self.bot_config = bot_config
        self.client = TNBApiClient(base_url=bot_config.api_base_url)
        self.wallets: Dict[str, Any] = {}
        self.tnb_balance = 0
        self.bot_run: Optional[BotRun] = None

    @staticmethod
    def analyze_order_book(order_book: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze order book and return insights."""
        if not order_book:
            logger.warning('Empty order book')
            return {}

        buy_orders = order_book.get('buy_orders', [])
        sell_orders = order_book.get('sell_orders', [])

        analysis: Dict[str, Any] = {
            'buy_orders_count': len(buy_orders),
            'sell_orders_count': len(sell_orders),
            'highest_buy': None,
            'lowest_sell': None,
            'spread': None
        }

        if buy_orders:
            highest_buy = max(buy_orders, key=lambda x: int(x.get('price', 0)))
            analysis['highest_buy'] = {'price': highest_buy.get('price'), 'quantity': highest_buy.get('quantity')}

        if sell_orders:
            lowest_sell = min(sell_orders, key=lambda x: int(x.get('price', float('inf'))))
            analysis['lowest_sell'] = {'price': lowest_sell.get('price'), 'quantity': lowest_sell.get('quantity')}

        highest_buy_data = analysis.get('highest_buy')
        lowest_sell_data = analysis.get('lowest_sell')
        if highest_buy_data and lowest_sell_data and isinstance(highest_buy_data,
                                                                dict) and isinstance(lowest_sell_data, dict):
            analysis['spread'] = int(lowest_sell_data['price']) - int(highest_buy_data['price'])

        return analysis

    def authenticate(self) -> bool:
        """Authenticate with the exchange API."""
        try:
            self.client.login(self.bot_config.api_username, self.bot_config.api_password)
            logger.info(f'Successfully authenticated bot: {self.bot_config.name}')
            return True
        except Exception as e:
            logger.error(f'Failed to authenticate bot {self.bot_config.name}: {e}')
            return False

    def create_bot_run(self) -> BotRun:
        """Create a new bot run record."""
        self.bot_run = BotRun.objects.create(bot_config=self.bot_config, status='running')
        return self.bot_run

    def decide_trade_action(self) -> Tuple[str, Optional[str]]:
        """Decide whether to buy or sell based on bot configuration."""
        non_tnb_currencies = self.get_non_tnb_currencies()

        if non_tnb_currencies and random.random() < self.bot_config.sell_probability:
            currency_to_sell = random.choice(list(non_tnb_currencies.keys()))
            return 'sell', currency_to_sell
        else:
            return 'buy', None

    def fetch_and_update_asset_pairs(self) -> List[AssetPair]:
        """Fetch asset pairs from API and update local cache."""
        try:
            api_pairs = self.client.get_asset_pairs()

            for api_pair in api_pairs:
                AssetPair.objects.update_or_create(
                    pair_id=api_pair.get('id'),
                    defaults={
                        'primary_currency_ticker': api_pair.get('primary_currency', {}).get('ticker', ''),
                        'secondary_currency_ticker': api_pair.get('secondary_currency', {}).get('ticker', ''),
                        'primary_currency_name': api_pair.get('primary_currency', {}).get('name', ''),
                        'secondary_currency_name': api_pair.get('secondary_currency', {}).get('name', ''),
                        'is_active': True,
                    }
                )

            return list(AssetPair.objects.filter(is_active=True))
        except Exception as e:
            logger.error(f'Failed to fetch asset pairs: {e}')
            return list(AssetPair.objects.filter(is_active=True))

    def fetch_wallet_info(self):
        """Fetch and update wallet information."""
        try:
            wallets = self.client.get_wallets()
            for wallet in wallets:
                currency = wallet.get('currency', {})
                currency_name = currency.get('ticker', 'Unknown')
                balance = wallet.get('balance', 0)
                self.wallets[currency_name] = balance

                if currency_name == 'TNB':
                    self.tnb_balance = int(balance)

            logger.info(f'Updated wallet balances for bot {self.bot_config.name}')
        except Exception as e:
            logger.error(f'Failed to fetch wallet info: {e}')

    def finalize_bot_run(self, status: str = 'completed', error_msg: str = ''):
        """Finalize the bot run with status and stats."""
        if self.bot_run:
            self.bot_run.ended_at = timezone.now()
            self.bot_run.status = status
            if error_msg:
                self.bot_run.errors = error_msg
            self.bot_run.save()

            # Update bot config last run time
            self.bot_config.last_run = timezone.now()
            self.bot_config.total_runs += 1
            self.bot_config.save()

    @staticmethod
    def get_asset_pair_for_currency(currency_ticker: str, asset_pairs: List[AssetPair]) -> Optional[AssetPair]:
        """Find the asset pair for a given currency ticker."""
        for pair in asset_pairs:
            if pair.primary_currency_ticker == currency_ticker:
                return pair
        return None

    def get_non_tnb_currencies(self) -> Dict[str, int]:
        """Get all non-TNB currencies with positive balance."""
        return {ticker: balance for ticker, balance in self.wallets.items() if ticker != 'TNB' and int(balance) > 0}

    def log_trade(
        self, asset_pair: AssetPair, side: str, price: Decimal, quantity: Decimal, order_response: Dict[str, Any]
    ):
        """Log a trade to the database."""
        if not self.bot_run:
            return

        TradeLog.objects.create(
            bot_run=self.bot_run,
            asset_pair=asset_pair,
            side=side,
            price=price,
            quantity=quantity,
            total_value=price * quantity,
            order_id=str(order_response.get('id', '')),
            status='executed' if order_response else 'failed',
            response_data=order_response
        )

    def place_order(
        self,
        asset_pair: AssetPair,
        order_book: Dict[str, Any],
        action: str = 'buy',
        currency_balance: int = 0
    ) -> bool:
        """Place a smart buy or sell order based on the order book."""
        buy_orders = order_book.get('buy_orders', [])
        sell_orders = order_book.get('sell_orders', [])

        if action == 'sell':
            side = -1  # SELL
            if not buy_orders:
                price = 10
                quantity = min(currency_balance, 50)
            else:
                highest_buy = max(buy_orders, key=lambda x: int(x.get('price', 0)))
                highest_price = int(highest_buy.get('price', 10))
                price = int(highest_price * 1.05)
                sell_percentage = random.uniform(0.25, 1.0)
                quantity = int(currency_balance * sell_percentage)
        else:
            side = 1  # BUY
            if not sell_orders:
                price = 4
                quantity = 20
            else:
                lowest_sell = min(sell_orders, key=lambda x: int(x.get('price', float('inf'))))
                lowest_price = int(lowest_sell.get('price', 5))
                price = int(lowest_price * 0.95)
                max_spend = min(int(self.tnb_balance * 0.1), int(self.bot_config.max_spend_per_trade))
                quantity = int(max_spend / price) if price > 0 else 0

        price = int(price)
        quantity = int(quantity)

        if quantity > 0 and price > 0:
            try:
                logger.info(f"Placing order: {'BUY' if side == 1 else 'SELL'} {quantity} @ {price} TNB")
                result = self.client.place_order(asset_pair.pair_id, price, quantity, side)
                self.log_trade(
                    asset_pair, 'BUY' if side == 1 else 'SELL', Decimal(str(price)), Decimal(str(quantity)), result
                )
                return True
            except Exception as e:
                logger.error(f'Failed to place order: {e}')
                return False
        else:
            logger.warning('Invalid order parameters, skipping order placement')
            return False


class RandyBotStrategy:
    """Randy bot specific trading strategy."""

    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service

    def execute_iteration(self) -> bool:
        """Execute one iteration of the Randy bot strategy."""
        try:
            # Fetch wallet information
            self.bot_service.fetch_wallet_info()

            # Get available asset pairs
            asset_pairs = self.bot_service.fetch_and_update_asset_pairs()
            if not asset_pairs:
                logger.error('No asset pairs available')
                return False

            # Decide trade action
            action, currency_to_sell = self.bot_service.decide_trade_action()
            logger.info(f'Trade decision: {action.upper()}' + (f' {currency_to_sell}' if currency_to_sell else ''))

            # Select appropriate asset pair
            if action == 'sell' and currency_to_sell:
                selected_pair = self.bot_service.get_asset_pair_for_currency(currency_to_sell, asset_pairs)
                if not selected_pair:
                    logger.warning(f'No asset pair found for {currency_to_sell}, falling back to buy')
                    action = 'buy'
                    selected_pair = random.choice(asset_pairs)
            else:
                selected_pair = random.choice(asset_pairs)

            logger.info(f'Selected asset pair: {selected_pair}')

            # Get order book
            order_book = self.bot_service.client.get_order_book(selected_pair.pair_id)
            analysis = self.bot_service.analyze_order_book(order_book)
            logger.info(f'Order book analysis: {analysis}')

            # Place order
            if action == 'sell' and currency_to_sell:
                currency_balance = int(self.bot_service.wallets.get(currency_to_sell, 0))
                if currency_balance > 0:
                    return self.bot_service.place_order(
                        selected_pair, order_book, action='sell', currency_balance=currency_balance
                    )
                else:
                    logger.warning(f'No balance for {currency_to_sell}, cannot sell')
                    return False
            elif self.bot_service.tnb_balance > self.bot_service.bot_config.min_balance_required:
                return self.bot_service.place_order(selected_pair, order_book, action='buy')
            else:
                logger.warning(f'Insufficient TNB balance: {self.bot_service.tnb_balance}')
                return False

        except Exception as e:
            logger.error(f'Error during bot iteration: {e}')
            return False
