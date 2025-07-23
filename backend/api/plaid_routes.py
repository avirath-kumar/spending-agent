from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, User, PlaidItem
from services.plaid_service import PlaidService
from services.transaction_sync import TransactionSyncService
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter(prefix="/plaid", tags=["plaid"])

# Pydantic models for request / response
class LinkTokenResponse(BaseModel):
    link_token: str

class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_name: str
    institution_id: str

class SyncResponse(BaseModel):
    success: bool
    added: int
    modified: int
    removed: int
    errors: list

# Initialize Plaid service
plaid_service = PlaidService()

@router.post("/link-token", response_model=LinkTokenResponse)
async def create_link_token(db: Session = Depends(get_db)):
    """Plaid Link needs link token to initialize"""
    # Hardcoded user for demo
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        link_token = plaid_service.create_link_token(user.id)
        return LinkTokenResponse(link_token=link_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange-token")
async def exchange_public_token(
    request: ExchangeTokenRequest,
    db: Session = Depends(get_db)
):
    """Get temp public token, exchange for permanent token, save bank connection"""
    user = db.query(User).filter(User.email == "demo@example.com").first()

    try:
        # Exchange token with plaid
        result = plaid_service.exchange_public_token(request.public_token)

        # Save to database
        plaid_item = PlaidItem(
            user_id=user.id,
            access_token=result['access_token'],
            item_id=result['item_id'],
            institution_id=request.institution_id,
            institution_name=request.institution_name
        )
        db.add(plaid_item)
        db.commit()

        # Do initial sync
        sync_service = TransactionSyncService(db)
        sync_result = sync_service.sync_item(plaid_item)

        return {
            "success": True,
            "message": f"Connected to {request.institution_name}",
            "sync_result": sync_result
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-transactions", response_model=SyncResponse)
async def sync_transactions(db: Session = Depends(get_db)):
    """Manually trigger a sync of all transactions"""
    user = db.query(User).filter(User.email == "demo@example.com").first()

    # Get all plaid items for user
    plaid_items = db.query(PlaidItem).filter(PlaidItem.user_id == user.id).all()

    if not plaid_items:
        raise HTTPException(status_code=404, detail="No connected accounts")
    
    total_summary = {
        'added': 0,
        'modified': 0,
        'removed': 0,
        'errors': []
    }

    sync_service = TransactionSyncService(db)

    for item in plaid_items:
        summary = sync_service.sync_item(item)
        total_summary['added'] += summary['added']
        total_summary['modified'] += summary['modified']
        total_summary['removed'] += summary['removed']
        total_summary['errors'].extend(summary['errors'])

    return SyncResponse(
        success=len(total_summary['errors']) == 0,
        **total_summary
    )

@router.get("/accounts")
async def get_accounts(db: Session = Depends(get_db)):
    """Get all connected accounts for the user"""
    user = db.query(User).filter(User.email == "demo@example.com").first()

    accounts = db.query(Account).join(PlaidItem).filter( # ERROR USED BUT NOT IMPORTED!!!!
        PlaidItem.user_id == user.id
    ).all()

    return [{
        'id': acc.id,
        'name': acc.name,
        'type': acc.type,
        'subtype': acc.subtype,
        'balance': acc.balance_current,
        'institution': acc.plaid_item.institution_name
    } for acc in accounts]