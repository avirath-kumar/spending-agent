from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Create database directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# SQLite connection string - just points to a file in directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Models - defining our tables as python classes
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    plaid_items = relationship("PlaidItem", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    thread_id = Column(String, index=True)  # For LangGraph integration
    messages = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="conversations")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plaid_transaction_id = Column(String, unique=True)
    account_id = Column(String)
    amount = Column(Float)
    date = Column(DateTime)
    name = Column(String)
    category = Column(JSON)  # Plaid provides array of categories
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship(Account, back_populates="transactions")

# Plaid item is a singular bank connection
class PlaidItem(Base):
    __tablename__ = "plaid_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    access_token = Column(String, unique=True)  # Encrypted token for API calls
    item_id = Column(String, unique=True)       # Plaid's ID for this connection
    institution_id = Column(String)             # Which bank
    institution_name = Column(String)           # Human-readable bank name
    cursor = Column(String)                     # For incremental syncs
    last_sync = Column(DateTime)                # Track sync status
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="plaid_items")
    accounts = relationship("Account", back_populates="plaid_item")

# Each bank connection can have multiple accounts (checking vs savings)
class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    plaid_item_id = Column(Integer, ForeignKey("plaid_items.id"))
    account_id = Column(String, unique=True)    # Plaid's account ID
    name = Column(String)                       # "Chase Checking"
    official_name = Column(String)              # "CHASE TOTAL CHECKING"
    type = Column(String)                       # "depository", "credit", etc.
    subtype = Column(String)                    # "checking", "savings", etc.
    balance_available = Column(Float)
    balance_current = Column(Float)
    balance_limit = Column(Float)               # For credit cards
    currency = Column(String, default="USD")
    
    # Relationships
    plaid_item = relationship("PlaidItem", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

# Create tables
Base.metadata.create_all(bind=engine)