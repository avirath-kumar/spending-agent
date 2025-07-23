from sqlalchemy.orm import Session
from database import PlaidItem, Account, Transaction
from services.plaid_service import PlaidService
from datetime import datetime
import json
from typing import List, Dict

# Orchestrates sync b/w Plaid and db - updating, inserting, removing transactions
class TransactionSyncService:
    
    def __init__(self, db: Session):
        self.db = db
        self.plaid = PlaidService()

    def sync_item(self, plaid_item: PlaidItem) -> Dict:
        """Full sync for a single bank connection"""
        sync_summary = {
            'added': 0,
            'modified': 0,
            'removed': 0,
            'errors': []
        }

        try:
            # First, sync accounts (may have changed)
            self._sync_accounts(plaid_item)

            # Then sync transactions
            has_more = True
            cursor = plaid_item.cursor

            while has_more:
                # Call plaid api
                sync_response = self.plaid.sync_transactions(
                    plaid_item.access_token,
                    cursor
                )

                # Process each type of upate
                sync_summary['added'] += len(sync_response['added'])
                sync_summary['modified'] += len(sync_response['modified'])
                sync_summary['removed'] += len(sync_response['removed'])

                # Handle added transactions
                for txn in sync_response['added']:
                    self._add_transaction(plaid_item, txn)
                
                # Handle modified transactions
                for txn in sync_response['modified']:
                    self._update_transaction(plaid_item, txn)
                
                # Handle removed transactions
                for txn in sync_response['removed']:
                    self._remove_transaction(txn['transaction_id'])
                
                # Update cursor for next sync
                cursor = sync_response['next_cursor']
                has_more = sync_response['has_more']

                # Commit after each page to avoid losing progress
                self.db.commit()
            
            # Update item's cursor and last sync time
            plaid_item.cursor = cursor
            plaid_item.last_sync = datetime.utcnow()
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            sync_summary['errors'].append(str(e))
        
        return sync_summary
    
    def _sync_accounts(self, plaid_item: PlaidItem):
        """Sync account info (balances, names, etc)"""
        accounts = self.plaid.get_accounts(plaid_item.access_token)

        for acc in accounts:
            # Check if account exists
            account = self.db.query(Account).filter(
                Account.account_id == acc['account_id']
            ).first()

            if not account:
                account = Account(
                    plaid_item_id=plaid_item.id,
                    account_id=acc['account_id']
                )
                self.db.add(account)
            
            # Update account info
            account.name = acc['name']
            account.official_name = acc.get('official_name')
            account.type = acc['type']
            account.subtype = acc['subtype']

            # Update balances
            balances = acc['balances']
            account.balance_available = balances.get('available')
            account.balance_current = balances.get('current')
            account.balance_limit = balances.get('limit')
            account.currency = balances.get('iso_currency_code', 'USD')
        
    def _add_transaction(self, plaid_item: PlaidItem, txn_data: Dict):
        "Add a new transaction to the database"
        # Find the account
        account = self.db.query(Account).filter(
            Account.plaid_item_id == plaid_item.id,
            Account.account_id == txn_data['account_id']
        ).first()

        if not account:
            return # skip if acct not found
        
        # Create transaction
        transaction = Transaction(
            user_id=plaid_item.user_id,
            plaid_transaction_id=txn_data['transaction_id'],
            account_id=account.id,
            amount=txn_data['amount'], #Plaid uses positives for expenses
            date=datetime.strptime(txn_data['date'], '%Y-%m-%d'),
            name=txn_data['name'],
            category=txn_data.get('category', [])
        )

        self.db.add(transaction)

    def _update_transaction(self, plaid_item: PlaidItem, txn_data: Dict):
        """Update an existing transaction"""
        transaction = self.db.query(Transaction).filter(
            Transaction.plaid_transaction_id == txn_data['transaction_id']
        ).first()

        if transaction:
            transaction.amount = txn_data['amount']
            transaction.date = datetime.strptime(txn_data['date'], '%Y-%m-%d')
            transaction.name = txn_data['name']
            transaction.category = txn_data.get('category', [])
    
    def _remove_transaction(self, transaction_id: str):
        """Remove a transaction bc plaid detected it was deleted/invalid"""
        transaction = self.db.query(Transaction).filter(
            Transaction.plaid_transaction_id == transaction_id
        ).first()

        if transaction:
            self.db.delete(transaction)