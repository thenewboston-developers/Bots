#!/usr/bin/env python3

import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv

from config.logging_config import setup_colored_logging
from thenewboston.api_client import TNBApiClient

load_dotenv()

setup_colored_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_number(value: int) -> str:
    """Format integer with thousands separator."""
    return f'{value:,}'


def get_sell_orders_by_currency(client: TNBApiClient) -> Dict[str, List[Dict]]:
    """
    Fetches all asset pairs and their order books, organizing sell orders by currency.
    Returns a dictionary mapping currency symbols to lists of market data.
    """
    logger.info('Fetching asset pairs...')
    asset_pairs = client.get_asset_pairs()

    currencies_with_sells = defaultdict(list)

    for pair in asset_pairs:
        asset_pair_id = pair['id']
        primary_currency = pair['primary_currency']['ticker']
        secondary_currency = pair['secondary_currency']['ticker']

        logger.info(f'Fetching order book for {primary_currency}/{secondary_currency} (ID: {asset_pair_id})...')

        try:
            order_book = client.get_order_book(asset_pair_id)

            # Check if there are sell orders
            if order_book.get('sell_orders') and len(order_book['sell_orders']) > 0:
                currencies_with_sells[primary_currency].append({
                    'asset_pair_id': asset_pair_id,
                    'pair_name': f'{primary_currency}/{secondary_currency}',
                    'secondary_currency': secondary_currency,
                    'sell_orders': order_book['sell_orders']
                })
        except Exception as e:
            logger.error(f'Failed to fetch order book for pair {asset_pair_id}: {e}')
            continue

    return currencies_with_sells


def generate_markdown_report(currencies_data: Dict[str, List[Dict]]) -> str:
    """Generate a markdown formatted report of sell orders by currency."""
    report_lines = []
    report_lines.append('# Sell Orders Report by Currency')
    report_lines.append(f'\n*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*\n')

    if not currencies_data:
        report_lines.append('No currencies with sell orders found.')
        return '\n'.join(report_lines)

    # Sort currencies alphabetically
    sorted_currencies = sorted(currencies_data.keys())

    # Add table of contents
    report_lines.append('## Table of Contents\n')
    for currency in sorted_currencies:
        report_lines.append(f'- [{currency}](#{currency.lower()})')
    report_lines.append('')

    # Add summary section
    report_lines.append('## Summary\n')
    report_lines.append(f'- **Total currencies with sell orders:** {len(currencies_data)}')
    total_markets = sum(len(markets) for markets in currencies_data.values())
    report_lines.append(f'- **Total markets with sell orders:** {total_markets}')
    report_lines.append('')

    # Add currencies with active sell orders
    report_lines.append('### Currencies with Active Sell Orders\n')
    report_lines.append(', '.join(sorted_currencies))
    report_lines.append('\n')

    # Generate detailed section for each currency
    report_lines.append('## Detailed Order Books\n')

    for currency in sorted_currencies:
        report_lines.append(f'### {currency}\n')

        for market_data in currencies_data[currency]:
            pair_name = market_data['pair_name']
            secondary = market_data['secondary_currency']
            sell_orders = market_data['sell_orders']

            report_lines.append(f'#### Market: {pair_name}\n')
            report_lines.append(f'**Number of sell orders:** {len(sell_orders)}\n')

            # Create order book table
            report_lines.append(f'| Amount ({currency}) | Price ({secondary}) | Total ({secondary}) |')
            report_lines.append('|------------------:|--------------------:|--------------------:|')

            # Sort sell orders by price (ascending)
            sorted_orders = sorted(sell_orders, key=lambda x: x['price'])

            # Calculate totals
            total_quantity = 0
            total_value = 0

            for order in sorted_orders[:15]:  # Show top 15 orders
                quantity = order['quantity']
                price = order['price']
                total = price * quantity

                total_quantity += quantity
                total_value += total

                report_lines.append(f'| {format_number(quantity)} | {format_number(price)} | {format_number(total)} |')

            if len(sorted_orders) > 15:
                report_lines.append(f'\n*... and {len(sorted_orders) - 15} more orders*')

            report_lines.append('')

            # Add statistics
            report_lines.append('**Statistics:**')
            report_lines.append(f'- Total quantity available: {format_number(total_quantity)} {currency}')
            report_lines.append(f'- Total market value: {format_number(total_value)} {secondary}')

            # Calculate min and max prices
            if sorted_orders:
                min_price = sorted_orders[0]['price']
                max_price = sorted_orders[-1]['price']
                report_lines.append(
                    f'- Price range: {format_number(min_price)} - {format_number(max_price)} {secondary}'
                )

                # Calculate spread if we had buy orders (we don't in this report)
                report_lines.append(f'- Lowest ask: {format_number(min_price)} {secondary}')

            report_lines.append('')

    return '\n'.join(report_lines)


def main():
    try:
        # Get credentials from environment (using Randy's by default for reports)
        username = os.getenv('RANDYS_USERNAME')
        password = os.getenv('RANDYS_PASSWORD')

        if not username or not password:
            raise ValueError('RANDYS_USERNAME and RANDYS_PASSWORD must be set in .env file')

        # Initialize API client and login
        client = TNBApiClient()
        logger.info(f'Logging in as {username}...')
        client.login(username, password)

        # Fetch data
        logger.info('Starting to fetch sell order data...')
        currencies_data = get_sell_orders_by_currency(client)

        # Generate markdown report
        report = generate_markdown_report(currencies_data)

        # Save report to markdown file in top level directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'order_book_sell_side_report_{timestamp}.md'
        with open(filename, 'w') as f:
            f.write(report)

        logger.info(f'Report saved to {filename}')

    except Exception as e:
        logger.error(f'Error generating report: {e}')
        raise


if __name__ == '__main__':
    main()
