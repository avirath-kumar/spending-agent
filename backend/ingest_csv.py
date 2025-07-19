import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, Transaction, User, engine
import sys
import os

def parse_date(date_str):
    """Parse date from MM/DD/YY format"""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y")
    except:
        return None

def clean_amount(amount):
    """Clean currency amount - handle negatives for expenses"""
    if pd.isna(amount):
        return 0.0
    # assume negative values are expenses
    return float(amount)

def ingest_transactions(csv_path: str, user_email: str = "demo@example.com"):
    """
    Ingest transactions from CSV file into database

    Why this exists: This is a one-time script to populate your database with test data.
    In production, this would be replaced by the Plaid API sync functionality.
    """
    # Create database session
    db = SessionLocal()

    try:
        # Get or create user
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            user = User(email=user_email)
            db.add(user)
            db.commit()
            print(f"Created user: {user_email}")
        
        # Read CSV file
        print(f"Reading CSV from: {csv_path}")
        df = pd.read_csv(csv_path)

        # Print columns info for debugging
        print(f"Columns found: {df.columns.tolist()}")
        print(f"Total rows: {len(df)}")

        # Process transactions
        transactions_added = 0
        for index, row in df.iterrows():
            # Parse transacitons data
            trans_date = parse_date(row['Date'])
            if not trans_date:
                print(f"Skipping row {index}: Invalid date")
                continue
        
            # Create transaction
            transaction = Transaction(
                user_id=user.id,
                # Using index as fake plaid_transaction_id for now
                plaid_transaction_id=f"test_trans_{index}",
                amount=clean_amount(row['Amount']),
                date=trans_date,
                name=row['Description'][:255] if pd.notna(row['Description']) else "Unknown",
                category=[row['Category']] if pd.notna(row['Category']) else ["Other"]
            )

            db.add(transaction)
            transactions_added += 1

            # Commit in batches
            if transactions_added % 10 == 0:
                db.commit()
                print(f"Added {transactions_added} transactions...")

        # Final commit
        print(f"\nSuccessfully ingested {transactions_added} transactions!")

        # Show summary
        total_spending = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.amount < 0
        ).count()

        total_income = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.amount > 0
        ).count()

        print(f"\nSummary for ueser {user_email}:")
        print(f"- Total expense transactions: {total_spending}")
        print(f"- Total income transactions: {total_income}")

    except Exception as e:
        print(f"Error during ingestion: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    # Run with: python backend/ingest_csv.py path/to/your.csv
    if len(sys.argv) < 2:
        print("Usage: python ingest_csv.py <csv_file_path>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found")
        sys.exit(1)
    
    ingest_transactions(csv_file)