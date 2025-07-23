import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional

# Encapsulates all plaid api interactions in one place
class PlaidService:
    
    # Configure plaid client
    def __init__(self):
        configuration = plaid.Configuration(
            host=getattr(plaid.Environment, os.getenv('PLAID_ENV', 'sandbox')),
            api_key={
                'clientId': os.getenv('PLAID_CLIENT_ID'),
                'secret': os.getenv('PLAID_SECRET'), # why is there a comma here?
            }
        )
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidAPI(api_client)

    # Create a token for Plaid link frontend widget
    def create_link_token(self, user_id: str) -> Dict:
        request = LinkTokenCreateRequest(
            products=[Products('transactions')], # this is what data we want
            client_name="PennyWise",
            country_codes=[CountryCode('US')],
            language='en',
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id))
            # do i need a webhook url?
        )

        response = self.client.link_token_create(request)
        return response['link_token']

    # User completes Plaid Link -> get public token (which we exchange for a permanent access token)
    def exchange_public_token(self, public_token: str) -> Dict:
        request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        response = self.client.item_public_token_exchange(request)
        return {
            'access_token': response['access_token'],
            'item_id': response['item_id']
        }

    # Fetches all accounts for a given bank connection
    def get_accounts(self, access_token: str) -> List[Dict]:
        request = AccountsGetRequest(access_token=access_token)
        response = self.client.accounts_get(request)
        return response['accounts']
    
    # Uses plaid's transaction sync endpoint for efficient updates. Cursor does incremental syncs
    def sync_transactions(self, access_token: str, cursor: Optional[str] = None) -> Dict:
        request = TransactionsSyncRequest(
            access_token=access_token,
            cursor=cursor # none for first sync, then use returned cursor
        )

        response = self.client.transactions_sync(request)

        return {
            'added': response['added'],
            'modified': response['modified'],
            'removed': response['removed'],
            'next_cursor': response['next_cursor'],
            'has_more': response['has_more']
        }