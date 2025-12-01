from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings


# 配置连接池以解决 MySQL 连接丢失问题
engine = create_engine(
    settings.database.url,
    echo=False,
    future=True,
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=3600,  # 连接回收时间（秒）
    connect_args={
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # novel | audio | comic
    jump_url: Mapped[Optional[str]] = mapped_column(String(255))
    cover_file_id: Mapped[Optional[str]] = mapped_column(Text)
    preview_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    preview_url: Mapped[Optional[str]] = mapped_column(String(512))
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    comic_files: Mapped[list["ComicFile"]] = relationship(
        "ComicFile", back_populates="resource", cascade="all, delete-orphan"
    )


class ComicFile(Base):
    __tablename__ = "comic_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    resource: Mapped[Resource] = relationship("Resource", back_populates="comic_files")


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    username: Mapped[Optional[str]] = mapped_column(String(64))
    vip_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_quota: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SearchLog(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(128), nullable=False)
    selected_filter: Mapped[str] = mapped_column(String(32), default="all")
    page_index: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SearchButton(Base):
    __tablename__ = "search_buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class VipPlan(Base):
    __tablename__ = "vip_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # 套餐名称，如 "月度VIP"
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)  # 时长（天）
    price: Mapped[float] = mapped_column(String(20), nullable=False)  # 价格（字符串，支持小数点）
    description: Mapped[Optional[str]] = mapped_column(Text)  # 描述
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PaymentConfig(Base):
    __tablename__ = "payment_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_type: Mapped[str] = mapped_column(String(16), nullable=False)  # wechat, alipay
    account_name: Mapped[Optional[str]] = mapped_column(String(128))  # 收款人姓名
    account_number: Mapped[Optional[str]] = mapped_column(String(128))  # 收款账号
    qr_code_url: Mapped[Optional[str]] = mapped_column(Text)  # 二维码图片URL
    qr_code_file_id: Mapped[Optional[str]] = mapped_column(Text)  # 二维码Telegram file_id
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "resources" in tables:
        columns = {col["name"] for col in inspector.get_columns("resources")}
        if "preview_url" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE resources ADD COLUMN preview_url VARCHAR(512)"))
        if "preview_message_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE resources ADD COLUMN preview_message_id BIGINT"))
    if "comic_files" in tables:
        columns = {col["name"] for col in inspector.get_columns("comic_files")}
        if "storage_message_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE comic_files ADD COLUMN storage_message_id BIGINT"))


def init_db():
    Base.metadata.create_all(bind=engine)
    ensure_schema()

