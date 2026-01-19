import os
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Numeric,
    ForeignKey, DateTime, func, Boolean, Date, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Carica variabili d'ambiente dal file .env
load_dotenv()

# Connessione al database PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id                    = Column(Integer, primary_key=True, autoincrement=True)
    username              = Column(String, unique=True, nullable=False)
    password_hash         = Column(Text, nullable=False)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    email                 = Column(String, unique=True, nullable=False)
    telegram_link_code    = Column(String, nullable=True)
    
    # 2FA Fields
    totp_secret           = Column(Text, nullable=True)       # Encrypted TOTP secret
    two_factor_enabled    = Column(Boolean, default=False)
    backup_codes          = Column(Text, nullable=True)       # Encrypted JSON array
    
    # Account Lockout Fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until          = Column(DateTime(timezone=True), nullable=True)
    last_failed_login     = Column(DateTime(timezone=True), nullable=True)
    
    # Password Reset Fields
    reset_token           = Column(String, nullable=True)
    reset_token_expires   = Column(DateTime(timezone=True), nullable=True)

    # Relazioni
    api_keys       = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    chats          = relationship("ChatSubscription", back_populates="user", cascade="all, delete-orphan")
    orders         = relationship("Order", back_populates="user", cascade="all, delete-orphan")


# NOTE: ChatSubscription class is defined below (after Order) to include 'enabled' field


class Exchange(Base):
    __tablename__ = "exchanges"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    api_keys = relationship("APIKey", back_populates="exchange")

class APIKey(Base):
    __tablename__ = "api_keys"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exchange_id = Column(Integer, ForeignKey("exchanges.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(100), nullable=True)  # Account name for easy identification
    api_key     = Column(Text, nullable=False)
    secret_key  = Column(Text, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    is_testnet  = Column(Boolean, default=False)
    user        = relationship("User", back_populates="api_keys")
    exchange    = relationship("Exchange", back_populates="api_keys")

class Order(Base):
    __tablename__ = "orders"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exchange_id    = Column(Integer, ForeignKey("exchanges.id"), nullable=True)  # Nullable per compatibilità con ordini esistenti
    symbol         = Column(String, nullable=False)
    side           = Column(String, nullable=False)
    quantity       = Column(Numeric, nullable=False)
    status         = Column(String, nullable=False)
    entry_price    = Column(Numeric, nullable=True)
    max_entry      = Column(Numeric, nullable=True)
    take_profit    = Column(Numeric, nullable=True)
    stop_loss      = Column(Numeric, nullable=True)
    entry_interval = Column(String, nullable=True)
    stop_interval  = Column(String, nullable=True)
    executed_price = Column(Numeric, nullable=True)
    executed_at    = Column(DateTime(timezone=True), nullable=True)
    closed_at      = Column(DateTime(timezone=True), nullable=True)
    sl_updated_at  = Column(DateTime(timezone=True), nullable=True)  # When SL/stop_interval was last modified
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    is_testnet     = Column(Boolean, default=False, nullable=False)
    tp_order_id    = Column(String, nullable=True)  # Binance TP order ID for accurate cancellation
    updating_until = Column(DateTime(timezone=True), nullable=True)  # Protected until this time during TP/SL updates

    user = relationship("User", back_populates="orders")
    exchange = relationship("Exchange")


class ChatSubscription(Base):
    """Telegram chat subscriptions for notifications"""
    __tablename__ = "chat_subscriptions"
    __table_args__ = {'extend_existing': True}
    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_id    = Column(String, nullable=False)  # Telegram chat ID
    enabled    = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chats")


class AuditLog(Base):
    """Security audit log for tracking sensitive operations"""
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}
    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action     = Column(String, nullable=False)  # login, logout, api_key_create, etc.
    details    = Column(Text, nullable=True)     # JSON details
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    success    = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    """Active user sessions for security monitoring"""
    __tablename__ = "user_sessions"
    __table_args__ = {'extend_existing': True}
    id            = Column(String, primary_key=True)  # UUID
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ip_address    = Column(String, nullable=True)
    user_agent    = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    is_active     = Column(Boolean, default=True)

    user = relationship("User")


class BalanceHistory(Base):
    """Tracks daily balance snapshots for statistics and charts"""
    __tablename__ = "balance_history"
    __table_args__ = (
        UniqueConstraint('user_id', 'date', 'exchange_id', 'is_testnet', name='uix_balance_history'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    usdc_balance = Column(Numeric(20, 8), default=0)
    crypto_value = Column(Numeric(20, 8), default=0)
    total_balance = Column(Numeric(20, 8), default=0)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False)
    is_testnet = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Funzione per inizializzare lo schema

def init_db():
    Base.metadata.create_all(bind=engine)


