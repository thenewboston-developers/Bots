import logging
from typing import Any, Dict, Generator, List, Optional

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

    def stream_asset_pairs(self, page_size: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Stream asset pairs one by one using pagination.

        This generator yields asset pairs individually to avoid loading all pairs
        into memory at once. It automatically handles pagination.

        Args:
            page_size: Optional page size for API requests (default uses API's default)

        Yields:
            Individual asset pair dictionaries

        Example:
            for pair in client.stream_asset_pairs():
                process_pair(pair)
        """
        page = 1
        total_pairs = 0

        while True:
            response = self.get_asset_pairs(page=page, page_size=page_size)
            pairs = response.get('results', [])

            for pair in pairs:
                total_pairs += 1
                yield pair

            if not response.get('next'):
                logger.info(f'Streamed {total_pairs} asset pairs across {page} pages')
                break
            page += 1

    def get_asset_pairs(self, page: Optional[int] = None, page_size: Optional[int] = None) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/asset-pairs'
        params = {}

        if page is not None:
            params['page'] = page
        if page_size is not None:
            params['page_size'] = page_size

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get asset pairs: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_currencies(
        self,
        no_wallet: Optional[bool] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        ordering: Optional[str] = None
    ) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/currencies'
        params = {}

        if no_wallet is not None:
            params['no_wallet'] = 'true' if no_wallet else 'false'
        if page is not None:
            params['page'] = str(page)
        if page_size is not None:
            params['page_size'] = str(page_size)
        if ordering is not None:
            params['ordering'] = ordering

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get currencies: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_currency(self, currency_id: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/currencies/{currency_id}'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            error_msg = f'Currency {currency_id} not found'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = f'Failed to get currency {currency_id}: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_exchange_orders(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/exchange-orders'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get exchange orders: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_order_book(self, asset_pair_id: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/exchange-orders/book'
        params = {'asset_pair': asset_pair_id}
        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get order book: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_platform_trade_history(self) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/trade-history-items'
        params = {'ordering': '-volume_24h'}
        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get platform trade history: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_posts(self, page: Optional[int] = None) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/posts'
        params = {}
        if page is not None:
            params['page'] = page

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get posts: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_trade_price_chart_data(self, asset_pair: int, time_range: str) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/trade-price-chart-data'
        params = {'asset_pair': str(asset_pair), 'time_range': time_range}

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            error_msg = f'Invalid request for chart data: {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = f'Failed to get chart data: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_transfers(self,
                      currency: int,
                      page: Optional[int] = None,
                      page_size: Optional[int] = None) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/transfers'
        params = {'currency': currency}

        if page is not None:
            params['page'] = page
        if page_size is not None:
            params['page_size'] = page_size

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            error_msg = 'Currency parameter is required for transfers'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = f'Failed to get transfers: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_user(self, user_id: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/users/{user_id}'
        # Users endpoint doesn't require authentication

        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            error_msg = f'User {user_id} not found'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = f'Failed to get user {user_id}: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/user/{user_id}/stats'
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            error_msg = f'User {user_id} not found'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = f'Failed to get user stats for {user_id}: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_users(self, page: Optional[int] = None, page_size: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = f'{self.base_url}/users'
        params = {}

        # Note: The API returns a list, not a paginated response
        # Parameters are kept for potential future API changes
        if page is not None:
            params['page'] = page
        if page_size is not None:
            params['page_size'] = page_size

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get users: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def stream_wallets(self, page_size: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Stream wallets one by one using pagination.

        This generator yields wallets individually to avoid loading all wallets
        into memory at once. It automatically handles pagination.

        Args:
            page_size: Optional page size for API requests (default uses API's default)

        Yields:
            Individual wallet dictionaries

        Example:
            for wallet in client.stream_wallets():
                process_wallet(wallet)
        """
        page = 1
        total_wallets = 0

        while True:
            response = self.get_wallets(page=page, page_size=page_size)
            wallets = response.get('results', [])

            for wallet in wallets:
                total_wallets += 1
                yield wallet

            if not response.get('next'):
                logger.info(f'Streamed {total_wallets} wallets across {page} pages')
                break
            page += 1

    def get_wallets(self, page: Optional[int] = None, page_size: Optional[int] = None) -> Dict[str, Any]:
        endpoint = f'{self.base_url}/wallets'
        params = {}

        if page is not None:
            params['page'] = page
        if page_size is not None:
            params['page_size'] = page_size

        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f'Failed to get wallets: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)

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
            error_msg = f'Failed to place order: {response.status_code} - {response.text}'
            logger.error(error_msg)
            raise ValueError(error_msg)
