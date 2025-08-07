import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class TNBApiClient:

    def __init__(self, base_url: str = 'https://thenewboston.network/api'):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
        })

    def get_asset_pairs(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/asset-pairs'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Failed to get asset pairs: {response.status_code} - {response.text}')
            return []

    def get_exchange_orders(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/exchange-orders'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Failed to get exchange orders: {response.status_code} - {response.text}')
            return []

    def get_order_book(self, asset_pair_id: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/exchange-orders/book'
        params = {'asset_pair': asset_pair_id}
        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Failed to get order book: {response.status_code} - {response.text}')
            return {}

    def get_trade_history(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/trade-history-items'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Failed to get trade history: {response.status_code} - {response.text}')
            return []

    def get_wallets(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/wallets'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Failed to get wallets: {response.status_code} - {response.text}')
            return []

    def login(self, username: str, password: str) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/login'
        payload = {'username': username, 'password': password}

        response = self.session.post(endpoint, json=payload)

        if response.status_code == 200:
            data = response.json()

            try:
                self.access_token = data['authentication']['access_token']
                self.session.headers['Authorization'] = f'Bearer {self.access_token}'
                logger.info(f'Successfully logged in as {username}')
                return data
            except KeyError:
                raise ValueError('Invalid login response: missing authentication.access_token')
        else:
            error_msg = f'Login failed: {response.status_code}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def place_order(self, asset_pair: int, price: int, quantity: int, side: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/exchange-orders'
        payload = {
            'asset_pair': asset_pair,
            'price': price,
            'quantity': quantity,
            'side': side  # 1 for BUY, -1 for SELL
        }

        response = self.session.post(endpoint, json=payload)

        if response.status_code in [200, 201]:
            logger.info(f'Order placed successfully: {payload}')
            return response.json()
        else:
            logger.error(f'Failed to place order: {response.status_code} - {response.text}')
            return response.json() if response.text else {}
