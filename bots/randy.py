import logging
import os
import random
from typing import Dict, Any

from dotenv import load_dotenv

from bots.api_client import TNBApiClient

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RandyBot:
    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.getenv("TNB_USERNAME")
        self.password = password or os.getenv("TNB_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("TNB_USERNAME and TNB_PASSWORD must be set in .env file or provided as arguments")

        self.client = TNBApiClient()
        self.wallets = {}
        self.tnb_balance = 0

    @staticmethod
    def analyze_order_book(order_book: Dict[str, Any]):
        if not order_book:
            logger.warning("Empty order book")
            return

        buy_orders = order_book.get("buy_orders", [])
        sell_orders = order_book.get("sell_orders", [])

        logger.info(f"Order book: {len(buy_orders)} buy orders, {len(sell_orders)} sell orders")

        if buy_orders:
            highest_buy = max(buy_orders, key=lambda x: int(x.get("price", 0)))
            logger.info(f"Highest buy: {highest_buy.get('price')} @ {highest_buy.get('quantity')}")

        if sell_orders:
            lowest_sell = min(sell_orders, key=lambda x: int(x.get("price", float('inf'))))
            logger.info(f"Lowest sell: {lowest_sell.get('price')} @ {lowest_sell.get('quantity')}")

    def fetch_wallet_info(self):
        wallets = self.client.get_wallets()
        if wallets:
            for wallet in wallets:
                currency = wallet.get("currency", {})
                currency_name = currency.get("ticker", "Unknown")
                balance = wallet.get("balance", 0)
                self.wallets[currency_name] = balance

                if currency_name == "TNB":
                    self.tnb_balance = int(balance)

            logger.info(f"Wallet balances: {self.wallets}")
            logger.info(f"TNB balance: {self.tnb_balance}")
        else:
            logger.warning("No wallet information retrieved")

    def place_smart_order(self, asset_pair_id: int, order_book: Dict[str, Any]):
        sell_orders = order_book.get("sell_orders", [])

        if not sell_orders:
            # No sell orders, place a buy order at a reasonable price
            price = 4
            quantity = 20
            side = 1  # Buy
        else:
            # Place a buy order slightly below the lowest sell
            lowest_sell = min(sell_orders, key=lambda x: int(x.get("price", float('inf'))))
            lowest_price = int(lowest_sell.get("price", 5))

            # Calculate order details
            price = int(lowest_price * 0.95)  # 5% below lowest sell
            max_spend = min(int(self.tnb_balance * 0.1), 100)  # Use max 10% of balance or 100 TNB
            quantity = int(max_spend / price) if price > 0 else 0
            side = 1  # Buy

        # Ensure reasonable values
        price = int(price)
        quantity = int(quantity)

        if quantity > 0 and price > 0:
            logger.info(f"Placing order: {'BUY' if side == 1 else 'SELL'} {quantity} @ {price} TNB")
            result = self.client.place_order(asset_pair_id, price, quantity, side)
            logger.info(f"Order result: {result}")
        else:
            logger.warning("Invalid order parameters, skipping order placement")

    def run(self):
        logger.info("Starting Randy Bot...")

        # Step 1: Login
        login_result = self.client.login(self.username, self.password)
        if "error" in login_result or "non_field_errors" in login_result:
            logger.error(f"Failed to login: {login_result}")
            return

        logger.info("Login successful!")

        # Step 2: Get wallet information
        self.fetch_wallet_info()

        # Step 3: Get trade history
        trade_history = self.client.get_trade_history()
        logger.info(f"Retrieved {len(trade_history)} trade history items")

        # Step 4: Get available asset pairs
        asset_pairs = self.client.get_asset_pairs()
        if not asset_pairs:
            logger.error("No asset pairs found. Cannot continue.")
            return

        # Step 5: Select a random asset pair
        random_pair = random.choice(asset_pairs)
        asset_pair_id = random_pair.get("id", 2)
        logger.info(f"Selected random asset pair: {asset_pair_id}")

        # Step 6: Get order book for the selected pair
        order_book = self.client.get_order_book(asset_pair_id)
        self.analyze_order_book(order_book)

        # Step 7: Place an order (if we have sufficient TNB balance)
        if self.tnb_balance > 100:  # Only place order if we have more than 100 TNB
            self.place_smart_order(asset_pair_id, order_book)
        else:
            logger.warning(f"Insufficient TNB balance: {self.tnb_balance}")


def main():
    bot = RandyBot()
    bot.run()


if __name__ == "__main__":
    main()
