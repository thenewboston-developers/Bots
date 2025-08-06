import json
import logging
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)


class TNBApiClient:
    def __init__(self, base_url: str = "https://thenewboston.network/api"):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token: Optional[str] = None

        # Set default headers
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://thenewboston.net",
            "Referer": "https://thenewboston.net/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"'
        })

    def get_asset_pairs(self) -> List[Dict[str, Any]]:
        endpoint = f"{self.base_url}/asset-pairs"
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get asset pairs: {response.status_code} - {response.text}")
            return []

    def get_order_book(self, asset_pair_id: int) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/exchange-orders/book"
        params = {"asset_pair": asset_pair_id}
        response = self.session.get(endpoint, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get order book: {response.status_code} - {response.text}")
            return {}

    def get_trade_history(self) -> List[Dict[str, Any]]:
        endpoint = f"{self.base_url}/trade-history-items"
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get trade history: {response.status_code} - {response.text}")
            return []

    def get_wallets(self) -> List[Dict[str, Any]]:
        endpoint = f"{self.base_url}/wallets"
        response = self.session.get(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get wallets: {response.status_code} - {response.text}")
            return []

    def login(self, username: str, password: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/login"
        payload = {
            "username": username,
            "password": password
        }

        logger.debug(f"Login payload: {json.dumps(payload)}")

        response = self.session.post(endpoint, json=payload)

        if response.status_code == 200:
            data = response.json()
            # Extract access token if present - check nested authentication object first
            if "authentication" in data and "access_token" in data["authentication"]:
                self.access_token = data["authentication"]["access_token"]
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            elif "access" in data:
                self.access_token = data["access"]
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            elif "token" in data:
                self.access_token = data["token"]
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            elif "access_token" in data:
                self.access_token = data["access_token"]
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            logger.info(f"Successfully logged in as {username}")
            return data
        else:
            logger.error(f"Login failed: {response.status_code} - {response.text}")
            try:
                return response.json()
            except:
                return {"error": response.text}

    def place_order(self, asset_pair: int, price: int, quantity: int, side: int) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/exchange-orders"
        payload = {
            "asset_pair": asset_pair,
            "price": price,
            "quantity": quantity,
            "side": side  # 1 for buy, 2 for sell
        }

        response = self.session.post(endpoint, json=payload)

        if response.status_code in [200, 201]:
            logger.info(f"Order placed successfully: {payload}")
            return response.json()
        else:
            logger.error(f"Failed to place order: {response.status_code} - {response.text}")
            return response.json() if response.text else {}
