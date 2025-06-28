# -*- coding: utf-8 -*-
import datetime
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.sql import func
from secrets import DATABASE_URL, SERVERS
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    subscriptions = relationship("Subscription", back_populates="user")

class Server(Base):
    __tablename__ = 'servers'
    id = Column(Integer, primary_key=True)
    region = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    subscriptions = relationship("Subscription", back_populates="server")

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    protocol = Column(String, nullable=False)
    key_data = Column(String, nullable=False)
    key_identifier = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    # Поле больше не используется, но оставляем для целостности схемы
    duration_months = Column(Integer, default=-1, nullable=False)
    user = relationship("User", back_populates="subscriptions")
    server = relationship("Server", back_populates="subscriptions")

# --- Настройка и функции БД ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_server_ids = {s.id for s in db.query(Server).all()}
        servers_added = 0
        for server_config in SERVERS:
            if server_config['id'] not in existing_server_ids:
                server = Server(
                    id=server_config['id'],
                    region=server_config['region'],
                    ip_address=server_config['ip']
                )
                db.add(server)
                servers_added += 1
        if servers_added > 0:
            db.commit()
            logger.info(f"Added {servers_added} new servers to the database.")
        else:
            logger.info("Servers table already up-to-date.")
    except Exception as e:
        logger.error(f"Error initializing servers in DB: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_user(db_session, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    db_user = db_session.query(User).filter(User.id == user_id).first()
    if not db_user:
        db_user = User(id=user_id, username=username, first_name=first_name, last_name=last_name)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
    elif (db_user.username != username or
          db_user.first_name != first_name or
          db_user.last_name != last_name):
         db_user.username = username
         db_user.first_name = first_name
         db_user.last_name = last_name
         db_session.commit()
    return db_user

def add_subscription(
        db_session: Session,
        user_id: int,
        server_id: int,
        protocol: str,
        key_data: str,
        key_identifier: str,
        expires_at: datetime.datetime
    ):

    sub = Subscription(
        user_id=user_id,
        server_id=server_id,
        protocol=protocol,
        key_data=key_data,
        expires_at=expires_at,
        key_identifier=key_identifier,
        is_active=True
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    logger.info(f"Key added for user {user_id}, server {server_id}, protocol {protocol}")
    return sub

def get_user_keys(db_session: Session, user_id: int) -> list[Subscription]:
    return db_session.query(Subscription).filter(
        Subscription.user_id == user_id
    ).order_by(Subscription.created_at.asc()).all()

def count_user_keys(db_session: Session, user_id: int) -> int:
    return db_session.query(Subscription).filter(
        Subscription.user_id == user_id
    ).count()