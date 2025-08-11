from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db, User, PlaidItem, Account
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

@router.post("/webhook")
async def plaid_webhook(request: dict):
    """Handle Plaid webhook events"""
    webhook_type = request.get('webhook_type')
    webhook_code = request.get('webhook_code')
    
    # Log webhook for debugging
    print(f"Plaid webhook: {webhook_type}.{webhook_code}")
    
    # Handle different webhook types
    if webhook_type == "TRANSACTIONS":
        # Handle transaction updates
        pass
    elif webhook_type == "ITEM":
        # Handle item updates (errors, etc.)
        pass
    
    return {"status": "received"}

@router.get("/accounts")
async def get_accounts(db: Session = Depends(get_db)):
    """Get all connected accounts for the user"""
    user = db.query(User).filter(User.email == "demo@example.com").first()

    accounts = db.query(Account).join(PlaidItem).filter(
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

@router.get("/link-page", response_class=HTMLResponse)
async def plaid_link_page(token: str):
    """
    Serve a simple HTML page that properly initializes Plaid Link.
    
    Why this exists: Plaid Link needs to run in a proper browser context,
    not inside an iframe. This page handles the Link flow and redirects
    back to your Streamlit app when complete.
    """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connect Your Bank - PennyWise</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                padding: 2rem;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }}
            h1 {{
                margin-bottom: 1rem;
            }}
            .status {{
                margin-top: 1rem;
                padding: 1rem;
                border-radius: 5px;
                display: none;
            }}
            .success {{
                background: rgba(72, 187, 120, 0.2);
                color: #48BB78;
            }}
            .error {{
                background: rgba(245, 101, 101, 0.2);
                color: #F56565;
            }}
            button {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 16px;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 1rem;
            }}
            button:hover {{
                background: #45a049;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 PennyWise</h1>
            <h2>Connect Your Bank Account</h2>
            <p>Click the button below to securely connect your bank account.</p>
            
            <button id="link-button" onclick="openLink()">
                🏦 Connect Bank Account
            </button>
            
            <div id="status" class="status"></div>
        </div>
        
        <script>
        let handler;
        
        // Initialize Plaid Link immediately
        window.onload = function() {{
            handler = Plaid.create({{
                token: '{token}',
                onSuccess: async (public_token, metadata) => {{
                    console.log('Success!', public_token, metadata);
                    
                    // Show success message
                    const status = document.getElementById('status');
                    status.className = 'status success';
                    status.style.display = 'block';
                    status.innerHTML = '✅ Successfully connected! Processing...';
                    
                    // Exchange the public token
                    try {{
                        const response = await fetch('/plaid/exchange-token', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{
                                public_token: public_token,
                                institution_name: metadata.institution.name,
                                institution_id: metadata.institution.institution_id
                            }})
                        }});
                        
                        if (response.ok) {{
                            status.innerHTML = '✅ Bank account connected! You can close this window.';
                            
                            // Optionally redirect back to Streamlit after a delay
                            setTimeout(() => {{
                                window.close();
                                // If window.close() doesn't work, redirect
                                window.location.href = 'http://localhost:8501/1_🏦_Connect_Bank';
                            }}, 2000);
                        }} else {{
                            throw new Error('Failed to exchange token');
                        }}
                    }} catch (error) {{
                        status.className = 'status error';
                        status.innerHTML = '❌ Error connecting account. Please try again.';
                    }}
                }},
                onLoad: () => {{
                    console.log('Plaid Link loaded');
                }},
                onExit: (err, metadata) => {{
                    console.log('Exit', err, metadata);
                    if (err) {{
                        const status = document.getElementById('status');
                        status.className = 'status error';
                        status.style.display = 'block';
                        status.innerHTML = '❌ ' + (err.display_message || 'Connection cancelled');
                    }}
                }},
                onEvent: (eventName, metadata) => {{
                    console.log('Event:', eventName, metadata);
                }}
            }});
            
            // Auto-open Link if desired
            // handler.open();
        }};
        
        function openLink() {{
            if (handler) {{
                handler.open();
            }}
        }}
        </script>
    </body>
    </html>
    """
    
    return html_content