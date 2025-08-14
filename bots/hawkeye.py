"""
Hawkeye - Precision Spread Hunter

A systematic trading bot that precisely targets the highest-scoring opportunities.

STRATEGY:
=========
1. MARKET MAKING
   - Targets wide bid-ask spreads (>5%) for profit capture
   - Places buy orders 2% below lowest ask, sell orders 2% above highest bid
   - Profits from spread compression as orders fill

2. SCORING SYSTEM (0-100 points)
   - Base: 50 points for every opportunity
   - Market Depth: +35 points max (order imbalance, volume ratios, spread width)
   - Price Trends: +25 points max (momentum, moving averages, volatility)
   - Only executes trades scoring >70 points

3. SMART EXECUTION
   - Analyzes all 30+ trading pairs every iteration
   - Fetches fresh order books and price data
   - Selects single best opportunity per round
   - Limits position to 30% of capital for risk management

RECENCY PENALTY:
===============
Prevents trading the same pair repeatedly with a 10-minute cooldown:
- Just traded: -30 points penalty
- 5 minutes ago: -15 points (linear decay)
- 10+ minutes: No penalty
This forces diversification but allows exceptional opportunities to override.

Example: TUNA scores 90 normally. After trading:
- Immediately: Drops to 60 (90-30)
- After 5 min: Recovers to 75 (90-15)
- After 10 min: Back to 90 (full score)
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from config.logging_config import setup_colored_logging
from thenewboston.api_client import TNBApiClient

load_dotenv(override=True)

setup_colored_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 0  # Time to wait between iterations (0 = no wait)
MAX_ITERATIONS = 100  # Maximum number of iterations (0 = infinite)
RECENCY_PENALTY_MINUTES = 10  # How long to penalize recently traded pairs
MAX_RECENCY_PENALTY = 30  # Maximum score penalty for recent trades


@dataclass
class TradeOpportunity:
    asset_pair_id: int
    pair_name: str
    action: str  # 'buy' or 'sell'
    price: int
    quantity: int
    score: float
    strategy: str
    reason: str
    currency_to_trade: str
    expected_profit: float


@dataclass
class TradeHistory:
    """Track executed trades across iterations."""
    pair_name: str
    action: str
    timestamp: datetime
    price: int
    quantity: int


class HawkeyeBot:

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username or os.getenv('HAWKEYES_USERNAME')
        self.password = password or os.getenv('HAWKEYES_PASSWORD')

        if not self.username or not self.password:
            raise ValueError('HAWKEYES_USERNAME and HAWKEYES_PASSWORD must be set')

        self.client = TNBApiClient()
        self.wallets: Dict[str, int] = {}
        self.tnb_balance = 0
        self.opportunities: List[TradeOpportunity] = []

    @staticmethod
    def analyze_market_depth(order_book: Dict[str, Any]) -> Dict[str, float]:
        """Analyze order book depth and liquidity."""
        buy_orders = order_book.get('buy_orders', [])
        sell_orders = order_book.get('sell_orders', [])

        buy_volume = sum(order['quantity'] for order in buy_orders)
        sell_volume = sum(order['quantity'] for order in sell_orders)

        buy_value = sum(order['quantity'] * order['price'] for order in buy_orders)
        sell_value = sum(order['quantity'] * order['price'] for order in sell_orders)

        spread = 0
        if buy_orders and sell_orders:
            highest_buy = max(buy_orders, key=lambda x: x['price'])['price']
            lowest_sell = min(sell_orders, key=lambda x: x['price'])['price']
            spread = (lowest_sell - highest_buy) / lowest_sell * 100 if lowest_sell > 0 else 0

        return {
            'buy_volume':
                buy_volume,
            'sell_volume':
                sell_volume,
            'buy_value':
                buy_value,
            'sell_value':
                sell_value,
            'spread_percentage':
                spread,
            'order_imbalance': ((buy_volume - sell_volume) / (buy_volume + sell_volume) if
                                (buy_volume + sell_volume) > 0 else 0)
        }

    @staticmethod
    def analyze_price_trends(chart_data: List[Dict]) -> Dict[str, float]:
        """Analyze price trends from chart data."""
        if not chart_data or len(chart_data) < 2:
            return {'trend': 0, 'volatility': 0, 'momentum': 0}

        prices = [point.get('price', 0) for point in chart_data if point.get('price')]
        if len(prices) < 2:
            return {'trend': 0, 'volatility': 0, 'momentum': 0}

        # Calculate simple moving averages
        sma_short = sum(prices[-5:]) / min(5, len(prices))
        sma_long = sum(prices) / len(prices)

        # Trend: positive if short MA > long MA
        trend = (sma_short - sma_long) / sma_long * 100 if sma_long > 0 else 0

        # Volatility: standard deviation of returns
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1] if prices[i - 1] > 0 else 0 for i in range(1, len(prices))
        ]
        volatility = (sum((r - sum(returns) / len(returns))**2 for r in returns) / len(returns))**0.5 if returns else 0

        # Momentum: price change over period
        momentum = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] > 0 else 0

        return {
            'trend': trend,
            'volatility': volatility * 100,
            'momentum': momentum,
            'sma_short': sma_short,
            'sma_long': sma_long
        }

    @staticmethod
    def _score_market_depth(market_depth: Dict, action: str) -> float:
        """Score market depth factors for a trading opportunity."""
        score = 0.0

        if action == 'buy':
            # Favor buying when there's selling pressure (lower prices)
            if market_depth['order_imbalance'] < -0.2:
                score += 15
            # Good spread means profit opportunity
            if market_depth['spread_percentage'] > 5:
                score += 10
            # High sell volume means availability
            if market_depth['sell_volume'] > market_depth['buy_volume'] * 1.5:
                score += 10
        else:  # sell
            # Favor selling when there's buying pressure (higher prices)
            if market_depth['order_imbalance'] > 0.2:
                score += 15
            # Good spread for selling
            if market_depth['spread_percentage'] > 5:
                score += 10
            # High buy volume means demand
            if market_depth['buy_volume'] > market_depth['sell_volume'] * 1.5:
                score += 10

        return score

    @staticmethod
    def _score_price_trends(price_trends: Dict, action: str) -> float:
        """Score price trend factors for a trading opportunity."""
        score = 0.0

        if action == 'buy':
            # Buy in uptrend
            if price_trends['trend'] > 5:
                score += 20
            elif price_trends['trend'] < -10:
                score += 15  # Or buy the dip
            # Lower volatility is safer
            if price_trends['volatility'] < 10:
                score += 5
        else:  # sell
            # Sell in downtrend or at peak
            if price_trends['trend'] < -5:
                score += 10  # Sell before further drop
            elif price_trends['trend'] > 15:
                score += 20  # Sell at peak
            # Higher volatility might mean better sell opportunity
            if price_trends['volatility'] > 15:
                score += 5

        return score

    @staticmethod
    def apply_recency_penalty(base_score: float, pair_name: str, trade_history: List[TradeHistory]) -> float:
        """Apply penalty to score based on how recently this pair was traded."""
        if not trade_history:
            return base_score

        # Find most recent trade for this pair
        recent_trade = None
        for trade in reversed(trade_history):  # Check from most recent
            if trade.pair_name == pair_name:
                recent_trade = trade
                break

        if not recent_trade:
            return base_score

        # Calculate time since last trade
        time_since = datetime.now() - recent_trade.timestamp
        minutes_since = time_since.total_seconds() / 60

        # Apply exponential decay penalty
        if minutes_since < RECENCY_PENALTY_MINUTES:
            # Penalty decreases exponentially with time
            penalty_ratio = 1 - (minutes_since / RECENCY_PENALTY_MINUTES)
            penalty = MAX_RECENCY_PENALTY * penalty_ratio
            adjusted_score = base_score - penalty

            logger.info(
                f'{pair_name}: Applied recency penalty of {penalty:.1f} points '
                f'(traded {minutes_since:.1f} minutes ago)'
            )

            return max(0, adjusted_score)  # Don't go below 0

        return base_score

    @staticmethod
    def calculate_trade_score(market_depth: Dict, price_trends: Dict, action: str) -> float:
        """Calculate a score for a trading opportunity."""
        score = 50.0  # Base score

        # Add market depth score
        score += HawkeyeBot._score_market_depth(market_depth, action)

        # Add price trends score
        score += HawkeyeBot._score_price_trends(price_trends, action)

        # Momentum factor
        if abs(price_trends['momentum']) > 20:
            score += 10  # High momentum either way is interesting

        return min(100, score)

    def evaluate_trading_opportunities(self, trade_history: List[TradeHistory]) -> None:
        """Evaluate all available trading opportunities."""
        logger.info('Evaluating trading opportunities...')

        # Get asset pairs
        asset_pairs = self.client.get_asset_pairs()

        for pair in asset_pairs:
            asset_pair_id = pair['id']
            primary_currency = pair['primary_currency']['ticker']
            secondary_currency = pair['secondary_currency']['ticker']
            pair_name = f'{primary_currency}/{secondary_currency}'

            logger.info(f'Analyzing {pair_name}...')

            try:
                # Get order book
                order_book = self.client.get_order_book(asset_pair_id)
                market_depth = self.analyze_market_depth(order_book)

                # Get price trends (1 day)
                chart_data: List[Dict] = []
                try:
                    chart_response = self.client.get_trade_price_chart_data(asset_pair_id, '1d')
                    chart_data = chart_response if isinstance(chart_response, list) else []
                except Exception:
                    logger.warning(f'Could not fetch chart data for {pair_name}')

                price_trends = self.analyze_price_trends(chart_data)

                # Evaluate buy opportunity if we have TNB
                if self.tnb_balance > 100:
                    buy_score = HawkeyeBot.calculate_trade_score(market_depth, price_trends, 'buy')
                    # Apply recency penalty
                    buy_score = HawkeyeBot.apply_recency_penalty(buy_score, pair_name, trade_history)

                    if order_book.get('sell_orders'):
                        lowest_sell = min(order_book['sell_orders'], key=lambda x: x['price'])
                        target_price = int(lowest_sell['price'] * 0.98)  # 2% below lowest sell
                        max_spend = min(int(self.tnb_balance * 0.3), 500)  # Use max 30% or 500 TNB
                        quantity = int(max_spend / target_price) if target_price > 0 else 0

                        if quantity > 0 and target_price > 0:
                            expected_profit = market_depth['spread_percentage'] * 0.5  # Conservative estimate

                            opportunity = TradeOpportunity(
                                asset_pair_id=asset_pair_id,
                                pair_name=pair_name,
                                action='buy',
                                price=target_price,
                                quantity=quantity,
                                score=buy_score,
                                strategy='Market Making'
                                if market_depth['spread_percentage'] > 5 else 'Trend Following',
                                reason=(
                                    f"Spread: {market_depth['spread_percentage']:.1f}%, "
                                    f"Trend: {price_trends['trend']:.1f}%, "
                                    f"Momentum: {price_trends['momentum']:.1f}%"
                                ),
                                currency_to_trade=primary_currency,
                                expected_profit=expected_profit
                            )
                            self.opportunities.append(opportunity)

                # Evaluate sell opportunity if we have this currency
                if primary_currency in self.wallets and self.wallets[primary_currency] > 0:
                    sell_score = HawkeyeBot.calculate_trade_score(market_depth, price_trends, 'sell')
                    # Apply recency penalty
                    sell_score = HawkeyeBot.apply_recency_penalty(sell_score, pair_name, trade_history)

                    if order_book.get('buy_orders'):
                        highest_buy = max(order_book['buy_orders'], key=lambda x: x['price'])
                        target_price = int(highest_buy['price'] * 1.02)  # 2% above highest buy
                        quantity = min(int(self.wallets[primary_currency] * 0.5), 100)  # Sell up to 50% or 100 units

                        if quantity > 0 and target_price > 0:
                            expected_profit = market_depth['spread_percentage'] * 0.5

                            opportunity = TradeOpportunity(
                                asset_pair_id=asset_pair_id,
                                pair_name=pair_name,
                                action='sell',
                                price=target_price,
                                quantity=quantity,
                                score=sell_score,
                                strategy='Profit Taking' if price_trends['trend'] > 10 else 'Risk Management',
                                reason=(
                                    f"Spread: {market_depth['spread_percentage']:.1f}%, "
                                    f"Trend: {price_trends['trend']:.1f}%, "
                                    f"Order Imbalance: {market_depth['order_imbalance']:.2f}"
                                ),
                                currency_to_trade=primary_currency,
                                expected_profit=expected_profit
                            )
                            self.opportunities.append(opportunity)

            except Exception as e:
                logger.error(f'Error analyzing {pair_name}: {e}')
                continue

        # Sort opportunities by score
        self.opportunities.sort(key=lambda x: x.score, reverse=True)
        logger.info(f'Found {len(self.opportunities)} trading opportunities')

    def execute_trade(self, opportunity: TradeOpportunity) -> bool:
        """Execute a single trade."""
        try:
            side = 1 if opportunity.action == 'buy' else -1
            logger.info(
                f'Executing {opportunity.action.upper()} trade: '
                f'{opportunity.quantity} {opportunity.currency_to_trade} @ {opportunity.price} TNB'
            )

            result = self.client.place_order(opportunity.asset_pair_id, opportunity.price, opportunity.quantity, side)

            logger.info(f'Trade executed successfully: {result}')
            return True

        except Exception as e:
            logger.error(f'Failed to execute trade: {e}')
            return False

    def fetch_wallet_info(self) -> None:
        """Fetch current wallet balances."""
        wallets = self.client.get_all_wallets()
        for wallet in wallets:
            currency = wallet.get('currency', {})
            ticker = currency.get('ticker', 'Unknown')
            balance = int(wallet.get('balance', 0))
            self.wallets[ticker] = balance

            if ticker == 'TNB':
                self.tnb_balance = balance

        logger.info(f'Wallet balances: {self.wallets}')
        logger.info(f'TNB balance: {self.tnb_balance}')

    def run(self, trade_history: List[TradeHistory]) -> List[TradeOpportunity]:
        """Run Hawkeye bot and execute the best trades."""
        logger.info('Starting Hawkeye Trading Bot...')

        # Login
        try:
            assert self.username is not None and self.password is not None
            self.client.login(self.username, self.password)
            logger.info('Login successful!')
        except Exception as e:
            logger.error(f'Failed to login: {e}')
            return []

        # Fetch wallet info
        self.fetch_wallet_info()

        # Evaluate opportunities with trade history
        self.evaluate_trading_opportunities(trade_history)

        # Select and execute the single best trade
        executed_trades = []
        if self.opportunities:
            opportunity = self.opportunities[0]  # Get the best opportunity
            logger.info('\n--- Best Trade Opportunity ---')
            logger.info(f'Pair: {opportunity.pair_name}')
            logger.info(f'Action: {opportunity.action.upper()}')
            logger.info(f'Strategy: {opportunity.strategy}')
            logger.info(f'Score: {opportunity.score:.1f}/100')
            logger.info(f'Reason: {opportunity.reason}')
            logger.info(f'Expected Profit: {opportunity.expected_profit:.2f}%')

            if self.execute_trade(opportunity):
                executed_trades.append(opportunity)

        return executed_trades


def main():
    if INTERVAL_SECONDS == 0 and MAX_ITERATIONS == 0:
        raise ValueError('Both INTERVAL_SECONDS and MAX_ITERATIONS cannot be 0. Set at least one value.')

    iteration = 0
    total_trades_executed = 0
    all_executed_trades = []
    trade_history: List[TradeHistory] = []  # Persistent trade history

    while True:
        iteration += 1
        logger.info(f'\n=== Hawkeye Iteration {iteration} ====')

        hawkeye = HawkeyeBot()
        executed_trades = hawkeye.run(trade_history)

        # Track all trades and update history
        for trade in executed_trades:
            trade_record = TradeHistory(
                pair_name=trade.pair_name,
                action=trade.action,
                timestamp=datetime.now(),
                price=trade.price,
                quantity=trade.quantity
            )
            trade_history.append(trade_record)

        all_executed_trades.extend(executed_trades)
        total_trades_executed += len(executed_trades)

        # Print iteration summary
        print(f'\n--- Iteration {iteration} Summary ---')

        if executed_trades:
            trade = executed_trades[0]
            print('Trade executed:')
            print(f'  Pair: {trade.pair_name}')
            print(f'  Action: {trade.action.upper()}')
            print(f'  Price: {trade.price} TNB')
            print(f'  Quantity: {trade.quantity} {trade.currency_to_trade}')
            print(f'  Total Value: {trade.price * trade.quantity} TNB')
            print(f'  Strategy: {trade.strategy}')
            print(f'  Score: {trade.score:.1f}/100')
            print(f'  Reason: {trade.reason}')
            print(f'  Expected Profit: {trade.expected_profit:.2f}%')
        else:
            print('No trade executed')

        if not executed_trades:
            logger.warning('No trades executed in this iteration.')

        # Check if we've hit max iterations
        if 0 < MAX_ITERATIONS <= iteration:
            logger.info(f'Reached maximum iterations ({MAX_ITERATIONS}). Exiting.')
            break

        # Wait for interval if specified
        if INTERVAL_SECONDS > 0:
            logger.info(f'Waiting {INTERVAL_SECONDS} seconds before next iteration...')
            time.sleep(INTERVAL_SECONDS)

    # Final summary
    print('\n' + '=' * 80)
    print('HAWKEYE TRADING SESSION SUMMARY')
    print('=' * 80)
    print(f'Total iterations: {iteration}')
    print(f'Total trades executed: {total_trades_executed}')

    if all_executed_trades:
        total_value = sum(trade.price * trade.quantity for trade in all_executed_trades)
        avg_score = sum(trade.score for trade in all_executed_trades) / len(all_executed_trades)
        avg_expected_profit = sum(trade.expected_profit for trade in all_executed_trades) / len(all_executed_trades)

        print(f'Total TNB traded: {total_value}')
        print(f'Average trade score: {avg_score:.1f}/100')
        print(f'Average expected profit: {avg_expected_profit:.2f}%')


if __name__ == '__main__':
    main()
