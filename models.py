import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Numeric,
    ForeignKey, DateTime, func, Boolean
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Connessione al database PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    username            = Column(String, unique=True, nullable=False)
    password_hash       = Column(Text, nullable=False)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    email               = Column(String, unique=True, nullable=False)
    telegram_link_code  = Column(String, nullable=True)

    # Relazioni
    api_keys       = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    chats          = relationship("ChatSubscription", back_populates="user", cascade="all, delete-orphan")
    orders         = relationship("Order", back_populates="user", cascade="all, delete-orphan")

class ChatSubscription(Base):
    __tablename__ = "chat_subscriptions"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_id    = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chats")

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
    api_key     = Column(Text, nullable=False)
    secret_key  = Column(Text, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    is_testnet = Column(Boolean, default=False)
    user     = relationship("User", back_populates="api_keys")
    exchange = relationship("Exchange", back_populates="api_keys")

class Order(Base):
    __tablename__ = "orders"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="orders")

# Funzione per inizializzare lo schema

def init_db():
    Base.metadata.create_all(bind=engine)

