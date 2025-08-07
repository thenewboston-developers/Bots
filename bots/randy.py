import logging
import os
import random
import time
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

from bots.api_client import TNBApiClient

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_CURRENCY_TICKER = 'TNB'
INTERVAL_SECONDS = 5  # Time to wait between iterations (0 = no wait)
MAX_ITERATIONS = 4  # Maximum number of iterations (0 = infinite)
SELL_PROBABILITY = 0.25  # % chance to sell non-TNB currencies


class RandyBot:

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username or os.getenv('TNB_USERNAME')
        self.password = password or os.getenv('TNB_PASSWORD')

        if not self.username or not self.password:
            raise ValueError('TNB_USERNAME and TNB_PASSWORD must be set in .env file or provided as arguments')

        self.client = TNBApiClient()
        self.wallets: Dict[str, Any] = {}
        self.tnb_balance = 0

    @staticmethod
    def analyze_order_book(order_book: Dict[str, Any]):
        if not order_book:
            logger.warning('Empty order book')
            return

        buy_orders = order_book.get('buy_orders', [])
        sell_orders = order_book.get('sell_orders', [])

        logger.info(f'Order book: {len(buy_orders)} buy orders, {len(sell_orders)} sell orders')

        if buy_orders:
            highest_buy = max(buy_orders, key=lambda x: int(x.get('price', 0)))
            logger.info(f"Highest buy: {highest_buy.get('price')} @ {highest_buy.get('quantity')}")

        if sell_orders:
            lowest_sell = min(sell_orders, key=lambda x: int(x.get('price', float('inf'))))
            logger.info(f"Lowest sell: {lowest_sell.get('price')} @ {lowest_sell.get('quantity')}")

    def decide_trade_action(self) -> Tuple[str, Optional[str]]:
        """Decide whether to buy or sell, and which currency to sell if selling.

        Returns:
            Tuple of (action, currency_ticker) where action is 'buy' or 'sell'
            and currency_ticker is the currency to sell (None if buying)
        """
        # Get non-TNB currencies with positive balance
        non_tnb_currencies = self.get_non_tnb_currencies()

        # If we have non-TNB currencies and random chance hits 25%
        if non_tnb_currencies and random.random() < SELL_PROBABILITY:
            # Pick a random non-TNB currency to sell
            currency_to_sell = random.choice(list(non_tnb_currencies.keys()))
            return 'sell', currency_to_sell
        else:
            # Otherwise buy
            return 'buy', None

    def fetch_wallet_info(self):
        wallets = self.client.get_wallets()
        for wallet in wallets:
            currency = wallet.get('currency', {})
            currency_name = currency.get('ticker', 'Unknown')
            balance = wallet.get('balance', 0)
            self.wallets[currency_name] = balance

            if currency_name == DEFAULT_CURRENCY_TICKER:
                self.tnb_balance = int(balance)

        logger.info(f'Wallet balances: {self.wallets}')
        logger.info(f'TNB balance: {self.tnb_balance}')

    @staticmethod
    def get_asset_pair_for_currency(currency_ticker: str, asset_pairs: list) -> Optional[Dict[str, Any]]:
        """Find the asset pair for a given currency ticker."""
        for pair in asset_pairs:
            # Check if this pair involves the currency we want to trade
            if pair.get('primary_currency', {}).get('ticker') == currency_ticker:
                return pair
        return None

    def get_non_tnb_currencies(self) -> Dict[str, int]:
        """Get all non-TNB currencies with positive balance."""
        return {
            ticker: balance
            for ticker, balance in self.wallets.items()
            if ticker != DEFAULT_CURRENCY_TICKER and int(balance) > 0
        }

    def place_smart_order(
        self, asset_pair_id: int, order_book: Dict[str, Any], action: str = 'buy', currency_balance: int = 0
    ):
        """Place a smart buy or sell order based on the order book.

        Args:
            asset_pair_id: The asset pair to trade
            order_book: The current order book
            action: 'buy' or 'sell'
            currency_balance: Balance of currency to sell (only used when action='sell')
        """
        buy_orders = order_book.get('buy_orders', [])
        sell_orders = order_book.get('sell_orders', [])

        if action == 'sell':
            # Selling logic
            side = -1  # SELL

            if not buy_orders:
                # No buy orders, place a sell order at a reasonable price
                price = 10  # Default sell price
                quantity = min(currency_balance, 50)  # Sell up to 50 units
            else:
                # Place a sell order slightly above the highest buy
                highest_buy = max(buy_orders, key=lambda x: int(x.get('price', 0)))
                highest_price = int(highest_buy.get('price', 10))

                # Price 5% above highest buy
                price = int(highest_price * 1.05)
                # Sell between 25% and 100% of holdings
                sell_percentage = random.uniform(0.25, 1.0)
                quantity = int(currency_balance * sell_percentage)
        else:
            # Buying logic (existing logic)
            side = 1  # BUY

            if not sell_orders:
                # No sell orders, place a buy order at a reasonable price
                price = 4
                quantity = 20
            else:
                # Place a buy order slightly below the lowest sell
                lowest_sell = min(sell_orders, key=lambda x: int(x.get('price', float('inf'))))
                lowest_price = int(lowest_sell.get('price', 5))

                # Calculate order details
                price = int(lowest_price * 0.95)  # 5% below lowest sell
                max_spend = min(int(self.tnb_balance * 0.1), 100)  # Use max 10% of balance or 100 TNB
                quantity = int(max_spend / price) if price > 0 else 0

        # Ensure reasonable values
        price = int(price)
        quantity = int(quantity)

        if quantity > 0 and price > 0:
            logger.info(f"Placing order: {'BUY' if side == 1 else 'SELL'} {quantity} @ {price} TNB")
            result = self.client.place_order(asset_pair_id, price, quantity, side)
            logger.info(f'Order result: {result}')
        else:
            logger.warning('Invalid order parameters, skipping order placement')

    def run(self):
        logger.info('Starting Randy Bot...')

        # Step 1: Login
        try:
            self.client.login(self.username, self.password)
            logger.info('Login successful!')
        except ValueError as e:
            logger.error(f'Failed to login: {e}')
            return

        # Step 2: Get wallet information
        self.fetch_wallet_info()

        # Step 3: Get platform trade history
        trade_history = self.client.get_platform_trade_history()
        logger.info(f'Retrieved {len(trade_history)} platform trade history items')

        # Step 4: Get available asset pairs
        asset_pairs = self.client.get_asset_pairs()
        if not asset_pairs:
            raise ValueError('No asset pairs found. Cannot continue.')

        # Step 5: Decide whether to buy or sell
        action, currency_to_sell = self.decide_trade_action()
        logger.info(f'Trade decision: {action.upper()}' + (f' {currency_to_sell}' if currency_to_sell else ''))

        # Step 6: Select appropriate asset pair
        if action == 'sell' and currency_to_sell:
            # Find the asset pair for the currency we want to sell
            selected_pair = RandyBot.get_asset_pair_for_currency(currency_to_sell, asset_pairs)
            if not selected_pair:
                logger.warning(f'No asset pair found for {currency_to_sell}, falling back to buy')
                action = 'buy'
                selected_pair = random.choice(asset_pairs)
        else:
            # Random pair for buying
            selected_pair = random.choice(asset_pairs)

        asset_pair_id = selected_pair.get('id', 2)
        logger.info(f'Selected asset pair: {asset_pair_id}')

        # Step 7: Get order book for the selected pair
        order_book = self.client.get_order_book(asset_pair_id)
        self.analyze_order_book(order_book)

        # Step 8: Place an order
        if action == 'sell' and currency_to_sell:
            # Get the balance of the currency to sell
            currency_balance = int(self.wallets.get(currency_to_sell, 0))
            if currency_balance > 0:
                self.place_smart_order(asset_pair_id, order_book, action='sell', currency_balance=currency_balance)
            else:
                logger.warning(f'No balance for {currency_to_sell}, cannot sell')
        elif self.tnb_balance > 100:  # Only buy if we have sufficient TNB
            self.place_smart_order(asset_pair_id, order_book, action='buy')
        else:
            logger.warning(f'Insufficient TNB balance: {self.tnb_balance}')


def main():
    if INTERVAL_SECONDS == 0 and MAX_ITERATIONS == 0:
        raise ValueError('Both INTERVAL_SECONDS and MAX_ITERATIONS cannot be 0. Set at least one value.')

    iteration = 0
    while True:
        iteration += 1
        logger.info(f'Starting iteration {iteration}')

        bot = RandyBot()
        bot.run()

        # Check if we've hit max iterations
        if MAX_ITERATIONS > 0 and iteration >= MAX_ITERATIONS:
            logger.info(f'Reached maximum iterations ({MAX_ITERATIONS}). Exiting.')
            break

        # Wait for interval if specified
        if INTERVAL_SECONDS > 0:
            logger.info(f'Waiting {INTERVAL_SECONDS} seconds before next iteration...')
            time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
