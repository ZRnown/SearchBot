from __future__ import annotations

import os
import zipfile
import tempfile
import shutil
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional
from pathlib import Path

import logging

try:
    import rarfile
    RAR_SUPPORT = True
except ImportError:
    RAR_SUPPORT = False

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlalchemy import String

from .config import settings
from .db import AdminUser, ComicFile, PaymentConfig, Resource, SearchButton, User, VipPlan, db_session, init_db


class ResourceResponse(BaseModel):
    id: str
    title: str
    type: str
    is_vip: bool
    link: str
    preview_link: Optional[str] = None
    deep_link: Optional[str] = None
    created_at: datetime


class ComicUploadResponse(BaseModel):
    id: str
    pages: int
    deep_link: str
    preview_link: Optional[str] = None


class ComicFileResponse(BaseModel):
    id: int
    file_id: str
    order: int


class ComicFilesResponse(BaseModel):
    resource_id: str
    title: str
    files: List[ComicFileResponse]


class UpdateComicFilesOrderRequest(BaseModel):
    file_orders: List[dict] = Field(..., description="List of {id: int, order: int}")


class SettingsResponse(BaseModel):
    page_size: int
    search_channel_id: int
    comic_preview_channel_id: int
    storage_channel_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileResponse(BaseModel):
    username: str


class UserResponse(BaseModel):
    user_id: int
    first_name: Optional[str]
    username: Optional[str]
    vip_expiry: Optional[datetime]
    is_blocked: bool
    usage_quota: int
    created_at: datetime
    updated_at: datetime


class UserCreateIn(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    vip_expiry: Optional[datetime] = None
    is_blocked: bool = False


class UserUpdateIn(BaseModel):
    first_name: Optional[str] = None
    username: Optional[str] = None
    vip_expiry: Optional[datetime] = None
    is_blocked: Optional[bool] = None


class VipPlanResponse(BaseModel):
    id: int
    name: str
    duration_days: int
    price: str
    description: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class VipPlanCreateIn(BaseModel):
    name: str
    duration_days: int
    price: str
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class VipPlanUpdateIn(BaseModel):
    name: Optional[str] = None
    duration_days: Optional[int] = None
    price: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class PaymentConfigResponse(BaseModel):
    id: int
    payment_type: str
    account_name: Optional[str]
    account_number: Optional[str]
    qr_code_url: Optional[str]
    qr_code_file_id: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PaymentConfigCreateIn(BaseModel):
    payment_type: str
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    qr_code_url: Optional[str] = None
    qr_code_file_id: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class PaymentConfigUpdateIn(BaseModel):
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    qr_code_url: Optional[str] = None
    qr_code_file_id: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class VipPaymentInfoResponse(BaseModel):
    plans: List[VipPlanResponse]
    wechat_config: Optional[PaymentConfigResponse] = None
    alipay_config: Optional[PaymentConfigResponse] = None


logger = logging.getLogger(__name__)
MAX_BCRYPT_BYTES = 72
# 配置 FastAPI 以支持大文件上传
app = FastAPI(
    title="Resource Admin Panel",
    # 注意：文件大小限制在 uvicorn 启动参数中配置
)
admin_bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode="HTML"),
)
_bot_username: Optional[str] = None
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
ALGORITHM = "HS256"

allowed_origins = os.getenv("ADMIN_PANEL_ORIGINS", "*")
origins = (
    ["*"]
    if allowed_origins.strip() == "*"
    else [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_BCRYPT_BYTES:
        logger.warning(
            "Admin password exceeds bcrypt 72-byte limit; extra bytes will be truncated."
        )
    return encoded[:MAX_BCRYPT_BYTES].decode("utf-8", "ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_normalize_password(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_normalize_password(plain_password), hashed_password)


def ensure_default_admin() -> None:
    with db_session() as session:
        admin = session.query(AdminUser).filter(AdminUser.username == settings.web_admin_user).first()
        if not admin:
            session.add(
                AdminUser(
                    username=settings.web_admin_user,
                    password_hash=hash_password(settings.web_admin_pass),
                )
            )


async def ensure_comic_preview_links() -> None:
    with db_session() as session:
        missing = (
            session.query(Resource)
            .filter(Resource.type == "comic")
            .filter((Resource.preview_url == None) | (Resource.preview_url == ""))
            .all()
        )
        if not missing:
            return
        bot_username = await get_bot_username()
        for resource in missing:
            resource.preview_url = f"https://t.me/{bot_username}?start=comic_{resource.id}"
        session.flush()


def create_access_token(*, subject: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {"sub": subject}
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.security.token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.security.jwt_secret, algorithm=ALGORITHM)


def require_admin(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=401,
        detail="无效的认证信息",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.security.jwt_secret, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username


class IndexedResourceIn(BaseModel):
    title: str = Field(..., max_length=255)
    type: str = Field(..., pattern="^(novel|audio)$")
    jump_url: str


class ResourceUpdateIn(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    jump_url: Optional[str] = None
    preview_url: Optional[str] = None


class IndexedResourceOut(BaseModel):
    id: str
    title: str
    type: str
    link: str


class SearchButtonIn(BaseModel):
    label: str = Field(..., max_length=64)
    url: str = Field(..., max_length=255)
    sort_order: int = Field(0, ge=0)


class SearchButtonResponse(BaseModel):
    id: int
    label: str
    url: str
    sort_order: int


async def get_bot_username() -> str:
    global _bot_username
    if _bot_username is None:
        me = await admin_bot.get_me()
        _bot_username = me.username or "MainBot"
    return _bot_username


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    ensure_default_admin()
    await ensure_comic_preview_links()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await admin_bot.session.close()


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


async def send_photo_with_retry(
    bot: Bot,
    chat_id: int,
    photo: BufferedInputFile | str,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> any:
    """发送图片，带重试机制和 Flood control 处理"""
    for attempt in range(max_retries):
        try:
            message = await bot.send_photo(chat_id, photo=photo)
            return message
        except TelegramRetryAfter as e:
            wait_time = e.retry_after + 1  # 多等1秒
            logger.warning(f"触发 Flood control，等待 {wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            if attempt < max_retries - 1:
                wait_time = initial_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"发送图片失败，{wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(wait_time)
            else:
                raise
    raise Exception(f"发送图片失败，已重试 {max_retries} 次")


async def delete_message_with_retry(
    bot: Bot,
    chat_id: int,
    message_id: int,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> bool:
    """删除消息，带重试机制和 Flood control 处理
    
    Returns:
        bool: True 如果删除成功，False 如果消息不存在或已被删除
    """
    for attempt in range(max_retries):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after + 1  # 多等1秒
            logger.warning(f"删除消息触发 Flood control，等待 {wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries}, message_id={message_id})")
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            error_message = str(e).lower()
            # 消息不存在或已被删除，这是正常的
            if "message to delete not found" in error_message or "message can't be deleted" in error_message:
                logger.info(f"消息 {message_id} 不存在或已被删除（正常情况）")
                return False
            # 其他错误，如果是最后一次尝试则返回 False，否则重试
            if attempt < max_retries - 1:
                wait_time = initial_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"删除消息失败，{wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries}, message_id={message_id}): {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"删除消息失败，已重试 {max_retries} 次 (message_id={message_id}): {e}")
                return False
    return False


def format_channel_id_for_link(channel_id: int) -> str:
    """将 Telegram 频道 ID 格式化为链接格式（去掉 -100 前缀）"""
    channel_str = str(abs(channel_id))
    if channel_str.startswith("100"):
        return channel_str[3:]  # 去掉 "100" 前缀
    return channel_str


def build_resource_link(resource: Resource, bot_username: Optional[str] = None) -> str:
    if resource.type in {"novel", "audio"}:
        return resource.jump_url or ""
    if resource.preview_url:
        return resource.preview_url
    if bot_username:
        return f"https://t.me/{bot_username}?start=comic_{resource.id}"
    if resource.preview_message_id:
        formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
        return f"https://t.me/c/{formatted_id}/{resource.preview_message_id}"
    return ""


def build_resource_response(resource: Resource, bot_username: Optional[str]) -> ResourceResponse:
    deep_link = (
        f"https://t.me/{bot_username}?start=comic_{resource.id}"
        if resource.type == "comic" and bot_username
        else None
    )
    preview_link = (
        resource.preview_url
        if resource.type == "comic"
        else resource.jump_url
    )
    if resource.type == "comic" and not preview_link and bot_username:
        preview_link = deep_link
    return ResourceResponse(
        id=resource.id,
        title=resource.title,
        type=resource.type,
        is_vip=resource.is_vip,
        link=build_resource_link(resource, bot_username),
        preview_link=preview_link,
        deep_link=deep_link,
        created_at=resource.created_at,
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    with db_session() as session:
        admin = session.query(AdminUser).filter(AdminUser.username == payload.username).first()
        if not admin or not verify_password(payload.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(subject=payload.username)
    return TokenResponse(
        access_token=token,
        expires_in=settings.security.token_expire_minutes * 60,
    )


@app.get("/auth/profile", response_model=ProfileResponse)
async def auth_profile(username: Annotated[str, Depends(require_admin)]):
    return ProfileResponse(username=username)


@app.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    username: Annotated[str, Depends(require_admin)],
):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位字符")
    with db_session() as session:
        admin = session.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin or not verify_password(payload.current_password, admin.password_hash):
            raise HTTPException(status_code=400, detail="当前密码错误")
        admin.password_hash = hash_password(payload.new_password)
        session.flush()
    return {"status": "ok"}


@app.get("/resources", response_model=List[ResourceResponse])
async def list_resources(
    _: Annotated[str, Depends(require_admin)],
    resource_type: Optional[str] = Query(None, regex="^(novel|audio|comic)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    bot_username = await get_bot_username()
    with db_session() as session:
        query = session.query(Resource)
        if resource_type:
            query = query.filter(Resource.type == resource_type)
        resources = query.order_by(Resource.created_at.desc()).offset(skip).limit(limit).all()
    return [build_resource_response(res, bot_username) for res in resources]


@app.get("/resources/count")
async def get_resources_count(
    _: Annotated[str, Depends(require_admin)],
    resource_type: Optional[str] = Query(None, regex="^(novel|audio|comic)$"),
):
    with db_session() as session:
        query = session.query(Resource)
        if resource_type:
            query = query.filter(Resource.type == resource_type)
        count = query.count()
    return {"count": count}


@app.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        resource = session.get(Resource, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # 删除预览频道的消息（支持媒体组，删除所有消息）
        preview_message_ids_to_delete = []
        if resource.preview_message_ids:
            # 如果有 preview_message_ids（新格式），使用它
            preview_message_ids_to_delete = resource.preview_message_ids
        elif resource.preview_message_id:
            # 向后兼容：只有 preview_message_id（旧格式）
            preview_message_ids_to_delete = [resource.preview_message_id]
        
        deleted_count = 0
        failed_count = 0
        for msg_id in preview_message_ids_to_delete:
            deleted = await delete_message_with_retry(
                bot=admin_bot,
                chat_id=settings.channels.comic_preview_channel_id,
                message_id=msg_id,
            )
            if deleted:
                deleted_count += 1
                logger.info(f"已删除预览频道消息: {msg_id}")
            else:
                failed_count += 1
                logger.warning(f"预览频道消息 {msg_id} 删除失败或不存在")
            # 添加小延迟避免触发速率限制
            await asyncio.sleep(0.1)
        
        if preview_message_ids_to_delete:
            logger.info(f"预览频道消息删除完成: 成功 {deleted_count}/{len(preview_message_ids_to_delete)}，失败 {failed_count}")
        
        # 对于漫画类型，删除仓库频道的消息
        if resource.type == "comic":
            comic_files = session.query(ComicFile).filter(ComicFile.resource_id == resource_id).all()
            total_files = len(comic_files)
            files_with_message_id = sum(1 for cf in comic_files if cf.storage_message_id)
            deleted_count = 0
            failed_count = 0
            
            logger.info(f"资源 {resource.id} 共有 {total_files} 个文件，其中 {files_with_message_id} 个有消息ID")
            
            for comic_file in comic_files:
                if comic_file.storage_message_id:
                    deleted = await delete_message_with_retry(
                        bot=admin_bot,
                        chat_id=settings.channels.storage_channel_id,
                        message_id=comic_file.storage_message_id,
                    )
                    if deleted:
                        deleted_count += 1
                        logger.info(f"已删除仓库频道消息: {comic_file.storage_message_id}")
                    else:
                        failed_count += 1
                        logger.warning(f"仓库频道消息 {comic_file.storage_message_id} 删除失败或不存在")
                    # 添加小延迟避免触发速率限制
                    await asyncio.sleep(0.1)
                else:
                    logger.warning(f"文件 {comic_file.id} (order={comic_file.order}) 没有 storage_message_id，无法删除")
            
            logger.info(f"资源 {resource.id} 删除完成: 成功 {deleted_count}/{files_with_message_id}，失败 {failed_count}，无消息ID {total_files - files_with_message_id}")
        
        session.delete(resource)
        session.flush()


@app.post("/resources/batch-delete", status_code=204, response_class=Response)
async def batch_delete_resources(
    resource_ids: Annotated[List[str], Body()],
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        resources = session.query(Resource).filter(Resource.id.in_(resource_ids)).all()
        for resource in resources:
            # 删除预览频道的消息（支持媒体组，删除所有消息）
            preview_message_ids_to_delete = []
            if resource.preview_message_ids:
                # 如果有 preview_message_ids（新格式），使用它
                preview_message_ids_to_delete = resource.preview_message_ids
            elif resource.preview_message_id:
                # 向后兼容：只有 preview_message_id（旧格式）
                preview_message_ids_to_delete = [resource.preview_message_id]
            
            deleted_count = 0
            failed_count = 0
            for msg_id in preview_message_ids_to_delete:
                deleted = await delete_message_with_retry(
                    bot=admin_bot,
                    chat_id=settings.channels.comic_preview_channel_id,
                    message_id=msg_id,
                )
                if deleted:
                    deleted_count += 1
                    logger.info(f"已删除预览频道消息: {msg_id}")
                else:
                    failed_count += 1
                    logger.warning(f"预览频道消息 {msg_id} 删除失败或不存在")
                # 添加小延迟避免触发速率限制
                await asyncio.sleep(0.1)
            
            if preview_message_ids_to_delete:
                logger.info(f"资源 {resource.id} 预览频道消息删除完成: 成功 {deleted_count}/{len(preview_message_ids_to_delete)}，失败 {failed_count}")
            
            # 对于漫画类型，删除仓库频道的消息
            if resource.type == "comic":
                comic_files = session.query(ComicFile).filter(ComicFile.resource_id == resource.id).all()
                total_files = len(comic_files)
                files_with_message_id = sum(1 for cf in comic_files if cf.storage_message_id)
                deleted_count = 0
                failed_count = 0
                
                logger.info(f"资源 {resource.id} 共有 {total_files} 个文件，其中 {files_with_message_id} 个有消息ID")
                
                for comic_file in comic_files:
                    if comic_file.storage_message_id:
                        deleted = await delete_message_with_retry(
                            bot=admin_bot,
                            chat_id=settings.channels.storage_channel_id,
                            message_id=comic_file.storage_message_id,
                        )
                        if deleted:
                            deleted_count += 1
                            logger.info(f"已删除仓库频道消息: {comic_file.storage_message_id}")
                        else:
                            failed_count += 1
                            logger.warning(f"仓库频道消息 {comic_file.storage_message_id} 删除失败或不存在")
                        # 添加小延迟避免触发速率限制
                        await asyncio.sleep(0.1)
                    else:
                        logger.warning(f"文件 {comic_file.id} (order={comic_file.order}) 没有 storage_message_id，无法删除")
                
                logger.info(f"资源 {resource.id} 删除完成: 成功 {deleted_count}/{files_with_message_id}，失败 {failed_count}，无消息ID {total_files - files_with_message_id}")
            
            # 删除资源（CASCADE 会自动删除关联的 comic_files）
            session.delete(resource)
        try:
            session.flush()
        except Exception as e:
            logger.error(f"删除资源时出错: {e}")
            session.rollback()
            raise HTTPException(status_code=500, detail=f"删除资源失败: {str(e)}")
    return Response(status_code=204)


@app.get("/search-buttons", response_model=List[SearchButtonResponse])
async def list_search_buttons(_: Annotated[str, Depends(require_admin)]) -> List[SearchButtonResponse]:
    with db_session() as session:
        buttons = (
            session.query(SearchButton)
            .order_by(SearchButton.sort_order.asc(), SearchButton.id.asc())
            .all()
        )
        return [
            SearchButtonResponse(
                id=button.id,
                label=button.label,
                url=button.url,
                sort_order=button.sort_order,
            )
            for button in buttons
        ]


@app.post("/search-buttons", response_model=SearchButtonResponse)
async def create_search_button(
    payload: SearchButtonIn,
    _: Annotated[str, Depends(require_admin)],
) -> SearchButtonResponse:
    label = payload.label.strip()
    url = payload.url.strip()
    if not label or not url:
        raise HTTPException(status_code=400, detail="按钮文本和链接不能为空")
    with db_session() as session:
        button = SearchButton(
            label=label,
            url=url,
            sort_order=payload.sort_order,
        )
        session.add(button)
        session.flush()
        return SearchButtonResponse(
            id=button.id,
            label=button.label,
            url=button.url,
            sort_order=button.sort_order,
        )


@app.put("/search-buttons/{button_id}", response_model=SearchButtonResponse)
async def update_search_button(
    button_id: int,
    payload: SearchButtonIn,
    _: Annotated[str, Depends(require_admin)],
) -> SearchButtonResponse:
    label = payload.label.strip()
    url = payload.url.strip()
    if not label or not url:
        raise HTTPException(status_code=400, detail="按钮文本和链接不能为空")
    with db_session() as session:
        button = session.get(SearchButton, button_id)
        if not button:
            raise HTTPException(status_code=404, detail="Button not found")
        button.label = label
        button.url = url
        button.sort_order = payload.sort_order
        session.flush()
        return SearchButtonResponse(
            id=button.id,
            label=button.label,
            url=button.url,
            sort_order=button.sort_order,
        )


@app.delete("/search-buttons/{button_id}", status_code=204, response_class=Response)
async def delete_search_button(
    button_id: int,
    _: Annotated[str, Depends(require_admin)],
) -> Response:
    with db_session() as session:
        button = session.get(SearchButton, button_id)
        if not button:
            raise HTTPException(status_code=404, detail="Button not found")
        session.delete(button)
        session.flush()
    return Response(status_code=204)


@app.post("/resources/indexed", response_model=IndexedResourceOut)
async def create_indexed_resource(
    payload: IndexedResourceIn, _: Annotated[str, Depends(require_admin)]
):
    with db_session() as session:
        resource = Resource(
            title=payload.title,
            type=payload.type,
            jump_url=payload.jump_url,
            is_vip=False,
        )
        session.add(resource)
        session.flush()
        return IndexedResourceOut(
            id=resource.id,
            title=resource.title,
            type=resource.type,
            link=build_resource_link(resource),
        )


@app.put("/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: str,
    payload: ResourceUpdateIn,
    _: Annotated[str, Depends(require_admin)],
):
    if (
        payload.title is None
        and payload.jump_url is None
        and payload.preview_url is None
    ):
        raise HTTPException(status_code=400, detail="未提供更新内容")
    with db_session() as session:
        resource = session.get(Resource, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        if payload.title is not None:
            resource.title = payload.title
        if resource.type in {"novel", "audio"}:
            if payload.jump_url is not None:
                resource.jump_url = payload.jump_url
            if payload.preview_url is not None:
                resource.preview_url = payload.preview_url
            resource.is_vip = False
        elif resource.type == "comic":
            if payload.preview_url is not None:
                resource.preview_url = payload.preview_url
            if payload.jump_url is not None:
                resource.jump_url = payload.jump_url
        else:
            raise HTTPException(status_code=400, detail="不支持的资源类型")
        session.flush()
    bot_username = await get_bot_username()
    return build_resource_response(resource, bot_username)


@app.post("/resources/comics", response_model=ComicUploadResponse)
async def upload_comic(
    title: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File(..., description="按文件名排序的图片列表")],
    _: Annotated[str, Depends(require_admin)],
    is_vip: Annotated[bool, Form()] = False,
    preview_count: Annotated[int, Form()] = 5,
):
    if not files:
        raise HTTPException(status_code=400, detail="至少上传一张图片")

    sorted_files = sorted(files, key=lambda f: f.filename or "")
    stored_file_ids: list[str] = []
    for idx, upload in enumerate(sorted_files, start=1):
        content = await upload.read()
        buffer = BufferedInputFile(content, filename=upload.filename or f"comic_{idx}.jpg")
        message = await admin_bot.send_photo(
            settings.channels.storage_channel_id,
            photo=buffer,
        )
        if not message.photo:
            raise HTTPException(status_code=500, detail="无法获取文件 ID")
        stored_file_ids.append(message.photo[-1].file_id)

    cover_file_id = stored_file_ids[0]
    bot_username = await get_bot_username()

    with db_session() as session:
        resource = Resource(
            title=title,
            type="comic",
            cover_file_id=cover_file_id,
            is_vip=is_vip,
            preview_url=None,  # 自动生成，不手动设置
        )
        session.add(resource)
        session.flush()

        deep_link = f"https://t.me/{bot_username}?start=comic_{resource.id}"
        
        # 发送前几张图片到预览频道，第一张图片的caption包含超链接
        preview_file_ids = stored_file_ids[:min(preview_count, len(stored_file_ids))]
        preview_messages = []
        for idx, file_id in enumerate(preview_file_ids):
            try:
                # 第一张图片添加caption（包含超链接），其他图片不添加caption
                if idx == 0:
                    caption = f'📖 <a href="{deep_link}">{title}</a>'
                    message = await admin_bot.send_photo(
                        settings.channels.comic_preview_channel_id,
                        photo=file_id,
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    message = await admin_bot.send_photo(
                        settings.channels.comic_preview_channel_id,
                        photo=file_id,
                    )
                preview_messages.append(message)
            except Exception as e:
                logger.error(f"发送预览图片失败: {e}")
                # 预览失败不影响主流程，继续执行
        
        # 如果有预览消息，使用第一个预览消息的链接并保存所有 message_id
        if preview_messages:
            preview_msg_id = preview_messages[0].message_id
            preview_msg_ids = [msg.message_id for msg in preview_messages]
            resource.preview_message_id = preview_msg_id  # 向后兼容
            resource.preview_message_ids = preview_msg_ids  # 存储所有消息ID
            formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
            resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
        else:
            resource.preview_url = deep_link
            
            for order, file_data in enumerate(stored_file_ids, start=1):
                if isinstance(file_data, tuple):
                    file_id, message_id = file_data
                else:
                    file_id = file_data
                    message_id = None
                session.add(
                    ComicFile(
                        resource_id=resource.id,
                        file_id=file_id,
                        order=order,
                        storage_message_id=message_id,
                    )
                )

        session.flush()
        logger.info(f"✅ 漫画创建成功: id={resource.id}, title={title}, deep_link={deep_link}")
        # db_session() 上下文管理器会在退出时自动提交
        return ComicUploadResponse(
            id=resource.id,
            pages=len(stored_file_ids),
            deep_link=deep_link,
            preview_link=resource.preview_url,
        )


def extract_images_from_archive(archive_path: Path, archive_type: str) -> tuple[List[Path], str]:
    """从压缩包中提取图片文件，返回图片文件列表和临时目录路径"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
    images = []
    extracted_dir = tempfile.mkdtemp()
    
    try:
        if archive_type == 'zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                namelist = zip_ref.namelist()
                logger.info(f"ZIP 文件包含 {len(namelist)} 个文件")
                image_count = 0
                for member in namelist:
                    member_path = Path(member)
                    if member_path.suffix.lower() in image_extensions:
                        # 提取到临时目录
                        zip_ref.extract(member, extracted_dir)
                        full_path = Path(extracted_dir) / member_path
                        if full_path.exists() and full_path.is_file():
                            images.append(full_path)
                            image_count += 1
                logger.info(f"ZIP 文件解压完成：成功提取 {image_count} 张图片")
        elif archive_type == 'rar':
            # 优先使用系统命令解压 RAR 文件，更可靠
            import subprocess
            import shutil as shutil_module
            
            # 尝试使用 unar 或 unrar 命令（跨平台支持）
            unar_cmd = None
            # 在 Linux 上，优先尝试 unrar，然后是 unar
            # 在 macOS 上，优先尝试 unar，然后是 unrar
            import platform
            system = platform.system().lower()
            if system == 'linux':
                cmd_order = ['unrar', 'unar']
            else:  # macOS, Windows 等
                cmd_order = ['unar', 'unrar']
            
            for cmd in cmd_order:
                try:
                    result = subprocess.run(
                        [cmd, '--version'] if cmd == 'unar' else [cmd],
                        capture_output=True,
                        timeout=5,
                        text=True
                    )
                    unar_cmd = cmd
                    logger.info(f"找到解压工具: {cmd} (系统: {system})")
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            if unar_cmd:
                # 使用系统命令解压
                try:
                    logger.info(f"使用 {unar_cmd} 解压 RAR 文件: {archive_path}")
                    if unar_cmd == 'unar':
                        # unar 命令格式: unar -o output_dir file.rar
                        result = subprocess.run(
                            [unar_cmd, '-o', extracted_dir, str(archive_path)],
                            capture_output=True,
                            timeout=300,  # 5分钟超时
                            text=True,
                            check=True
                        )
                    else:  # unrar
                        # unrar 命令格式: unrar x file.rar output_dir/
                        result = subprocess.run(
                            [unar_cmd, 'x', '-y', str(archive_path), f'{extracted_dir}/'],
                            capture_output=True,
                            timeout=300,
                            text=True,
                            check=True
                        )
                    
                    logger.info(f"{unar_cmd} 解压成功")
                    
                    # 扫描解压后的文件
                    for root, dirs, files in os.walk(extracted_dir):
                        for file in files:
                            file_path = Path(root) / file
                            if file_path.suffix.lower() in image_extensions:
                                if file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0:
                                    images.append(file_path)
                    
                    image_count = len(images)
                    logger.info(f"RAR 文件解压完成：成功提取 {image_count} 张图片")
                    
                    if image_count == 0:
                        raise ValueError("RAR 文件中未找到图片文件")
                        
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else e.stdout if e.stdout else str(e)
                    logger.error(f"{unar_cmd} 解压失败: {error_msg}")
                    raise ValueError(f"使用 {unar_cmd} 解压 RAR 文件失败: {error_msg}")
                except subprocess.TimeoutExpired:
                    raise ValueError(f"解压 RAR 文件超时（超过 5 分钟）")
                except Exception as e:
                    logger.error(f"解压 RAR 文件时出错: {e}")
                    raise ValueError(f"解压 RAR 文件失败: {str(e)}")
            elif RAR_SUPPORT:
                # 回退到 rarfile 库（作为备用方案）
                logger.warning("未找到系统解压工具，使用 rarfile 库（可能不稳定）")
                try:
                    with rarfile.RarFile(archive_path, 'r') as rar_ref:
                        try:
                            namelist = rar_ref.namelist()
                        except Exception as e:
                            raise ValueError(f"无法读取 RAR 文件列表: {str(e)}。建议安装 unar 工具: brew install unar")
                        
                        if not namelist:
                            raise ValueError("RAR 文件为空：无法读取文件列表")
                        
                        logger.info(f"RAR 文件包含 {len(namelist)} 个文件")
                        image_count = 0
                        for member in namelist:
                            member_path = Path(member)
                            if member_path.suffix.lower() in image_extensions:
                                try:
                                    # 尝试使用 open 方法直接读取（更可靠）
                                    with rar_ref.open(member) as f:
                                        content = f.read()
                                        if content:
                                            full_path = Path(extracted_dir) / member_path
                                            full_path.parent.mkdir(parents=True, exist_ok=True)
                                            with open(full_path, 'wb') as out:
                                                out.write(content)
                                            if full_path.exists() and full_path.stat().st_size > 0:
                                                images.append(full_path)
                                                image_count += 1
                                except Exception as e:
                                    logger.warning(f"解压文件 {member} 失败: {e}")
                                    continue
                        
                        if image_count == 0:
                            raise ValueError("RAR 文件中未找到图片文件或所有文件解压失败。建议安装 unar 工具: brew install unar")
                        logger.info(f"使用 rarfile 库解压完成：成功提取 {image_count} 张图片")
                except Exception as e:
                    raise ValueError(f"解压 RAR 文件失败: {str(e)}。建议安装 unar 工具: brew install unar")
            else:
                raise ValueError("无法解压 RAR 文件：未找到解压工具。请安装 unar: brew install unar 或 unrar 工具")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的压缩包格式: {archive_type}")
    except Exception as e:
        logger.error(f"解压失败: {e}")
        # 清理临时目录
        try:
            shutil.rmtree(extracted_dir)
        except:
            pass
        raise HTTPException(status_code=400, detail=f"解压失败: {str(e)}")
    
    # 过滤掉 macOS 隐藏文件（以 ._ 开头的文件）和其他系统文件
    images = [img for img in images if not img.name.startswith('._') and not img.name.startswith('.DS_Store')]
    
    # 按文件名排序
    images.sort(key=lambda p: str(p.name).lower())
    return images, extracted_dir


@app.post("/resources/comics/archive", response_model=ComicUploadResponse)
async def upload_comic_archive(
    title: Annotated[str, Form()],
    archive: Annotated[UploadFile, File(..., description="压缩包文件 (zip/rar)")],
    _: Annotated[str, Depends(require_admin)],
    is_vip: Annotated[bool, Form()] = False,
    preview_count: Annotated[int, Form()] = 5,
):
    """上传压缩包并自动解压、发送到存储频道和预览频道"""
    if not archive.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 判断压缩包类型
    filename_lower = archive.filename.lower()
    if filename_lower.endswith('.zip'):
        archive_type = 'zip'
    elif filename_lower.endswith('.rar'):
        if not RAR_SUPPORT:
            raise HTTPException(status_code=400, detail="RAR 格式需要安装 rarfile 库")
        archive_type = 'rar'
    else:
        raise HTTPException(status_code=400, detail="仅支持 zip 和 rar 格式")
    
    # 保存压缩包到临时文件（流式处理，避免大文件内存溢出）
    logger.info(f"开始接收压缩包: {archive.filename}, 大小: {archive.size if hasattr(archive, 'size') else '未知'}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{archive_type}") as tmp_archive:
        tmp_archive_path = Path(tmp_archive.name)
        # 流式读取，避免一次性加载到内存
        chunk_size = 1024 * 1024  # 1MB chunks
        total_size = 0
        # 移除文件大小限制，支持大文件上传（2GB+）
        max_size = 2 * 1024 * 1024 * 1024  # 2GB 限制（可根据需要调整）
        while True:
            chunk = await archive.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size:
                raise HTTPException(status_code=413, detail=f"文件大小超过限制 ({max_size / 1024 / 1024 / 1024:.1f}GB)")
            tmp_archive.write(chunk)
            tmp_archive.flush()  # 立即刷新缓冲区
            # 每 100MB 记录一次进度
            if total_size % (100 * 1024 * 1024) < chunk_size:
                logger.info(f"接收进度: {total_size / 1024 / 1024:.2f}MB")
        
        # 确保所有数据都写入磁盘
        tmp_archive.flush()
        os.fsync(tmp_archive.fileno())  # 强制同步到磁盘
        logger.info(f"压缩包接收完成: {archive.filename}, 实际大小: {total_size / 1024 / 1024:.2f}MB")
        
        # 验证文件是否完整
        actual_file_size = tmp_archive_path.stat().st_size
        if actual_file_size != total_size:
            raise HTTPException(status_code=400, detail=f"文件写入不完整: 期望 {total_size} 字节，实际 {actual_file_size} 字节")
    
    extracted_dir = None
    try:
        # 解压并提取图片
        image_files, extracted_dir = extract_images_from_archive(tmp_archive_path, archive_type)
        if not image_files:
            raise HTTPException(status_code=400, detail="压缩包中未找到图片文件")
        
        # 发送所有图片到存储频道（使用媒体组批量发送，每10张一组）
        stored_file_ids: list[tuple[str, int]] = []
        # Telegram 限制：媒体组最多10个文件
        chunk_size_media = 10
        for i in range(0, len(image_files), chunk_size_media):
            chunk = image_files[i:i + chunk_size_media]
            media_group = []
            for img_path in chunk:
                with open(img_path, 'rb') as f:
                    img_content = f.read()
                buffer = BufferedInputFile(img_content, filename=img_path.name)
                media_group.append(InputMediaPhoto(media=buffer))
            
            try:
                # 使用媒体组批量发送
                messages = await admin_bot.send_media_group(
                    settings.channels.storage_channel_id,
                    media=media_group,
                )
                # 从返回的消息中提取 file_id 和 message_id
                for message in messages:
                    if message.photo:
                        stored_file_ids.append((message.photo[-1].file_id, message.message_id))
                logger.info(f"成功发送媒体组: {len(messages)} 张图片")
                # 每组之间稍作延迟，避免触发 Flood control
                if i + chunk_size_media < len(image_files):
                    await asyncio.sleep(0.5)
            except TelegramRetryAfter as e:
                wait_time = e.retry_after + 1
                logger.warning(f"触发 Flood control，等待 {wait_time} 秒")
                await asyncio.sleep(wait_time)
                # 重试发送这一组
                messages = await admin_bot.send_media_group(
                    settings.channels.storage_channel_id,
                    media=media_group,
                )
                for message in messages:
                    if message.photo:
                        stored_file_ids.append((message.photo[-1].file_id, message.message_id))
            except Exception as e:
                logger.error(f"发送媒体组失败: {e}")
                raise HTTPException(status_code=500, detail=f"发送图片失败: {str(e)}")
        
        # 提取 file_id（如果是元组则取第一个元素）
        cover_file_id = stored_file_ids[0][0] if isinstance(stored_file_ids[0], tuple) else stored_file_ids[0]
        bot_username = await get_bot_username()
        
        with db_session() as session:
            resource = Resource(
                title=title,
                type="comic",
                cover_file_id=cover_file_id,
                is_vip=is_vip,
                preview_url=None,  # 自动生成，不手动设置
            )
            session.add(resource)
            session.flush()
            
            deep_link = f"https://t.me/{bot_username}?start=comic_{resource.id}"
            
            # 发送前几张图片到预览频道（作为一条媒体组消息），第一张图片的caption包含超链接
            # stored_file_ids 里的元素可能是 file_id 或 (file_id, message_id) 元组，这里统一只取 file_id
            preview_file_ids = [
                (item[0] if isinstance(item, tuple) else item)
                for item in stored_file_ids[:min(preview_count, len(stored_file_ids))]
            ]
            preview_messages = []
            if preview_file_ids:
                try:
                    # 第一张图片添加caption（包含超链接），其他图片不添加caption
                    media_group = []
                    for idx, file_id in enumerate(preview_file_ids):
                        if idx == 0:
                            caption = f'📖 <a href="{deep_link}">{title}</a>'
                            media_group.append(
                                InputMediaPhoto(
                                    media=file_id,
                                    caption=caption,
                                    parse_mode="HTML",
                                )
                            )
                        else:
                            media_group.append(InputMediaPhoto(media=file_id))
                    messages = await admin_bot.send_media_group(
                        settings.channels.comic_preview_channel_id,
                        media=media_group,
                    )
                    preview_messages.extend(messages)
                except Exception as e:
                    logger.error(f"发送预览图片失败: {e}")
                    # 预览失败不影响主流程，继续执行
            
            # 如果有预览消息，使用第一个预览消息的链接并保存所有 message_id
            if preview_messages:
                preview_msg_id = preview_messages[0].message_id
                preview_msg_ids = [msg.message_id for msg in preview_messages]
                resource.preview_message_id = preview_msg_id  # 向后兼容
                resource.preview_message_ids = preview_msg_ids  # 存储所有消息ID
                formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
                resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
            else:
                resource.preview_url = deep_link
            
            for order, file_data in enumerate(stored_file_ids, start=1):
                if isinstance(file_data, tuple):
                    file_id, message_id = file_data
                else:
                    file_id = file_data
                    message_id = None
                session.add(
                    ComicFile(
                        resource_id=resource.id,
                        file_id=file_id,
                        order=order,
                        storage_message_id=message_id,
                    )
                )
            
            session.flush()
            logger.info(f"✅ 漫画创建成功: id={resource.id}, title={title}, deep_link={deep_link}")
            # db_session() 上下文管理器会在退出时自动提交
            return ComicUploadResponse(
                id=resource.id,
                pages=len(stored_file_ids),
                deep_link=deep_link,
                preview_link=resource.preview_url,
            )
    finally:
        # 清理临时文件
        try:
            if tmp_archive_path.exists():
                tmp_archive_path.unlink()
        except:
            pass
        try:
            if extracted_dir and Path(extracted_dir).exists():
                shutil.rmtree(extracted_dir)
        except:
            pass


@app.post("/resources/comics/batch-archive", response_model=List[ComicUploadResponse])
async def batch_upload_comic_archives(
    archives: Annotated[list[UploadFile], File(..., description="压缩包文件列表 (zip/rar)")],
    _: Annotated[str, Depends(require_admin)],
    is_vip: Annotated[bool, Form()] = False,
    preview_count: Annotated[int, Form()] = 5,
):
    """批量上传压缩包并自动解压、发送到存储频道和预览频道"""
    try:
        logger.info(f"收到批量上传请求: {len(archives) if archives else 0} 个文件")
        if not archives:
            logger.error("批量上传请求：没有文件")
            raise HTTPException(status_code=400, detail="至少上传一个压缩包")
        
        # 记录文件信息
        for idx, archive in enumerate(archives):
            if archive.filename:
                logger.info(f"文件 {idx+1}: {archive.filename}, 大小: {archive.size if hasattr(archive, 'size') else '未知'}")
        
        # 检查 RAR 支持
        if not RAR_SUPPORT:
            rar_files = [f.filename for f in archives if f.filename and f.filename.lower().endswith('.rar')]
            if rar_files:
                logger.error(f"检测到 RAR 文件但未安装 rarfile 库: {rar_files}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"RAR 格式需要安装 rarfile 库。请运行: pip install rarfile"
                )
        
        results = []
        processed_count = 0
        skipped_count = 0
        for archive in archives:
            processed_count += 1
            logger.info(f"处理文件 {processed_count}/{len(archives)}: {archive.filename if archive.filename else '无文件名'}")
            if not archive.filename:
                logger.warning(f"文件 {processed_count}: 跳过（无文件名）")
                skipped_count += 1
                continue
            
            # 判断压缩包类型
            filename_lower = archive.filename.lower()
            if filename_lower.endswith('.zip'):
                archive_type = 'zip'
            elif filename_lower.endswith('.rar'):
                if not RAR_SUPPORT:
                    logger.warning(f"跳过 {archive.filename}: RAR 格式需要安装 rarfile 库")
                    skipped_count += 1
                    continue
                archive_type = 'rar'
            else:
                logger.warning(f"跳过 {archive.filename}: 仅支持 zip 和 rar 格式（当前扩展名: {Path(archive.filename).suffix}）")
                skipped_count += 1
                continue
            
            # 使用文件名（去掉扩展名）作为标题
            title = Path(archive.filename).stem
            
            # 保存压缩包到临时文件（流式处理，避免大文件内存溢出）
            logger.info(f"开始接收压缩包: {archive.filename}, 大小: {archive.size if hasattr(archive, 'size') else '未知'}")
            tmp_archive_path = None
            file_too_large = False
            total_size = 0
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{archive_type}") as tmp_archive:
                    tmp_archive_path = Path(tmp_archive.name)
                    # 流式读取，避免一次性加载到内存
                    chunk_size = 1024 * 1024  # 1MB chunks
                    # 移除文件大小限制，支持大文件上传（2GB+）
                    max_size = 2 * 1024 * 1024 * 1024  # 2GB 限制（可根据需要调整）
                    chunk_count = 0
                    while True:
                        chunk = await archive.read(chunk_size)
                        if not chunk:
                            break
                        chunk_count += 1
                        total_size += len(chunk)
                        if total_size > max_size:
                            logger.warning(f"跳过 {archive.filename}: 文件大小超过限制 ({max_size / 1024 / 1024 / 1024:.1f}GB)")
                            file_too_large = True
                            # 跳出循环，跳过这个文件
                            break
                        tmp_archive.write(chunk)
                        tmp_archive.flush()  # 立即刷新缓冲区，确保数据写入磁盘
                        # 每 100MB 记录一次进度
                        if total_size % (100 * 1024 * 1024) < chunk_size:
                            logger.info(f"接收进度 {archive.filename}: {total_size / 1024 / 1024:.2f}MB")
                    
                    # 确保所有数据都写入磁盘
                    tmp_archive.flush()
                    os.fsync(tmp_archive.fileno())  # 强制同步到磁盘
                    
                    if total_size == 0:
                        logger.error(f"跳过 {archive.filename}: 文件为空（可能文件数据未正确传输）")
                        file_too_large = True  # 使用这个标志来跳过空文件
                        skipped_count += 1
                    else:
                        logger.info(f"压缩包接收完成: {archive.filename}, 实际大小: {total_size / 1024 / 1024:.2f}MB")
                        # 验证文件是否完整（检查文件大小是否匹配）
                        if hasattr(archive, 'size') and archive.size and total_size != archive.size:
                            logger.warning(f"文件大小不匹配: {archive.filename}, 期望: {archive.size}, 实际: {total_size}")
                        # 验证文件是否真的存在且可读
                        if tmp_archive_path.exists():
                            actual_file_size = tmp_archive_path.stat().st_size
                            if actual_file_size != total_size:
                                logger.error(f"文件写入不完整: {archive.filename}, 期望: {total_size}, 实际文件大小: {actual_file_size}")
                                file_too_large = True
                                skipped_count += 1
            except Exception as e:
                logger.error(f"接收压缩包 {archive.filename} 时出错: {e}", exc_info=True)
                if tmp_archive_path and tmp_archive_path.exists():
                    try:
                        tmp_archive_path.unlink()
                    except:
                        pass
                continue
            
            # 如果文件超过大小限制，跳过处理
            if file_too_large:
                if tmp_archive_path and tmp_archive_path.exists():
                    try:
                        tmp_archive_path.unlink()
                    except:
                        pass
                skipped_count += 1
                continue
            
            if not tmp_archive_path or not tmp_archive_path.exists():
                logger.warning(f"跳过 {archive.filename}: 临时文件不存在")
                skipped_count += 1
                continue
            
            # 在解压前验证文件完整性
            try:
                actual_size = tmp_archive_path.stat().st_size
                if actual_size == 0:
                    logger.error(f"跳过 {archive.filename}: 临时文件大小为 0")
                    skipped_count += 1
                    if tmp_archive_path.exists():
                        try:
                            tmp_archive_path.unlink()
                        except:
                            pass
                    continue
                if total_size > 0 and actual_size != total_size:
                    logger.error(f"跳过 {archive.filename}: 文件写入不完整，期望: {total_size} 字节，实际: {actual_size} 字节")
                    skipped_count += 1
                    if tmp_archive_path.exists():
                        try:
                            tmp_archive_path.unlink()
                        except:
                            pass
                    continue
                logger.info(f"临时文件验证通过: {archive.filename}, 大小: {actual_size / 1024 / 1024:.2f}MB")
            except Exception as e:
                logger.error(f"验证临时文件失败 {archive.filename}: {e}")
                skipped_count += 1
                continue
            
            extracted_dir = None
            try:
                # 解压并提取图片
                logger.info(f"开始解压: {archive.filename}, 文件大小: {tmp_archive_path.stat().st_size} 字节")
                image_files, extracted_dir = extract_images_from_archive(tmp_archive_path, archive_type)
                if not image_files:
                    logger.warning(f"跳过 {archive.filename}: 压缩包中未找到图片文件（解压后的文件列表为空）")
                    skipped_count += 1
                    continue
                logger.info(f"解压成功: {archive.filename}, 找到 {len(image_files)} 张图片")
                
                # 发送所有图片到存储频道（使用媒体组批量发送，每10张一组）
                stored_file_ids: list[tuple[str, int]] = []
                # Telegram 限制：媒体组最多10个文件
                media_chunk_size = 10
                for i in range(0, len(image_files), media_chunk_size):
                    chunk = image_files[i:i + media_chunk_size]
                    media_group = []
                    for img_path in chunk:
                        with open(img_path, 'rb') as f:
                            img_content = f.read()
                        buffer = BufferedInputFile(img_content, filename=img_path.name)
                        media_group.append(InputMediaPhoto(media=buffer))
                    
                    try:
                        # 使用媒体组批量发送
                        messages = await admin_bot.send_media_group(
                            settings.channels.storage_channel_id,
                            media=media_group,
                        )
                        # 从返回的消息中提取 file_id 和 message_id
                        for message in messages:
                            if message.photo:
                                stored_file_ids.append((message.photo[-1].file_id, message.message_id))
                        logger.info(f"成功发送媒体组: {len(messages)} 张图片")
                        # 每组之间稍作延迟，避免触发 Flood control
                        if i + media_chunk_size < len(image_files):
                            await asyncio.sleep(0.5)
                    except TelegramRetryAfter as e:
                        wait_time = e.retry_after + 1
                        logger.warning(f"触发 Flood control，等待 {wait_time} 秒")
                        await asyncio.sleep(wait_time)
                        # 重试发送这一组
                        messages = await admin_bot.send_media_group(
                            settings.channels.storage_channel_id,
                            media=media_group,
                        )
                        for message in messages:
                            if message.photo:
                                stored_file_ids.append((message.photo[-1].file_id, message.message_id))
                    except Exception as e:
                        logger.error(f"发送媒体组失败: {e}")
                        raise HTTPException(status_code=500, detail=f"发送图片失败: {str(e)}")
                
                # 提取 file_id（如果是元组则取第一个元素）
                cover_file_id = stored_file_ids[0][0] if isinstance(stored_file_ids[0], tuple) else stored_file_ids[0]
                bot_username = await get_bot_username()
                
                with db_session() as session:
                    resource = Resource(
                        title=title,
                        type="comic",
                        cover_file_id=cover_file_id,
                        is_vip=is_vip,
                        preview_url=None,
                    )
                    session.add(resource)
                    session.flush()
                    
                    deep_link = f"https://t.me/{bot_username}?start=comic_{resource.id}"
                    
                    # 发送前几张图片到预览频道（作为一条媒体组消息），第一张图片的caption包含超链接
                    # 提取 file_id（如果是元组则取第一个元素）
                    preview_file_ids = [
                        (item[0] if isinstance(item, tuple) else item) 
                        for item in stored_file_ids[:min(preview_count, len(stored_file_ids))]
                    ]
                    preview_messages = []
                    if preview_file_ids:
                        try:
                            # 第一张图片添加caption（包含超链接），其他图片不添加caption
                            media_group = []
                            for idx, file_id in enumerate(preview_file_ids):
                                if idx == 0:
                                    caption = f'📖 <a href="{deep_link}">{title}</a>'
                                    media_group.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML"))
                                else:
                                    media_group.append(InputMediaPhoto(media=file_id))
                            messages = await admin_bot.send_media_group(
                                settings.channels.comic_preview_channel_id,
                                media=media_group,
                            )
                            preview_messages.extend(messages)
                        except Exception as e:
                            logger.error(f"发送预览图片失败: {e}")
                    
                    if preview_messages:
                        preview_msg_id = preview_messages[0].message_id
                        preview_msg_ids = [msg.message_id for msg in preview_messages]
                        resource.preview_message_id = preview_msg_id  # 向后兼容
                        resource.preview_message_ids = preview_msg_ids  # 存储所有消息ID
                        formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
                        resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
                    else:
                        resource.preview_url = deep_link
                    
                    for order, file_data in enumerate(stored_file_ids, start=1):
                        if isinstance(file_data, tuple):
                            file_id, message_id = file_data
                        else:
                            file_id = file_data
                            message_id = None
                        session.add(
                            ComicFile(
                                resource_id=resource.id,
                                file_id=file_id,
                                order=order,
                                storage_message_id=message_id,
                            )
                        )
                    
                    session.flush()
                    logger.info(f"✅ 漫画创建成功: id={resource.id}, title={title}, deep_link={deep_link}")
                    # db_session() 上下文管理器会在退出时自动提交
                    results.append(ComicUploadResponse(
                        id=resource.id,
                        pages=len(stored_file_ids),
                        deep_link=deep_link,
                        preview_link=resource.preview_url,
                    ))
            except Exception as e:
                logger.error(f"处理压缩包 {archive.filename} 失败: {e}", exc_info=True)
                # 继续处理下一个，不中断批量上传
            finally:
                # 清理临时文件
                try:
                    if tmp_archive_path and tmp_archive_path.exists():
                        tmp_archive_path.unlink()
                except:
                    pass
                try:
                    if extracted_dir and Path(extracted_dir).exists():
                        shutil.rmtree(extracted_dir)
                except:
                    pass
        
        if not results:
            logger.error(f"批量上传：没有成功上传任何压缩包（处理: {processed_count}, 跳过: {skipped_count}, 成功: {len(results)}）")
            raise HTTPException(
                status_code=400, 
                detail=f"没有成功上传任何压缩包。处理了 {processed_count} 个文件，跳过了 {skipped_count} 个文件。请检查文件格式、大小和内容。"
            )
        
        logger.info(f"批量上传完成: 成功 {len(results)} 个文件")
        return results
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"批量上传处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量上传处理失败: {str(e)}")


@app.get("/resources/comics/{resource_id}/files", response_model=ComicFilesResponse)
async def get_comic_files(
    resource_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    """获取漫画的图片列表"""
    with db_session() as session:
        resource = session.get(Resource, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        if resource.type != "comic":
            raise HTTPException(status_code=400, detail="Resource is not a comic")
        
        files = session.query(ComicFile).filter(
            ComicFile.resource_id == resource_id
        ).order_by(ComicFile.order).all()
        
        return ComicFilesResponse(
            resource_id=resource.id,
            title=resource.title,
            files=[
                ComicFileResponse(
                    id=file.id,
                    file_id=file.file_id,
                    order=file.order,
                )
                for file in files
            ],
        )


@app.get("/resources/comics/files/{file_id}/url")
async def get_comic_file_url(
    file_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    """获取 Telegram 图片的 URL"""
    try:
        file = await admin_bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
        return {"url": file_url}
    except Exception as e:
        logger.error(f"获取文件 URL 失败: {e}")
        raise HTTPException(status_code=404, detail="文件不存在或无法访问")


@app.put("/resources/comics/{resource_id}/files/order", status_code=204, response_class=Response)
async def update_comic_files_order(
    resource_id: str,
    payload: UpdateComicFilesOrderRequest,
    _: Annotated[str, Depends(require_admin)],
):
    """更新漫画图片的顺序"""
    with db_session() as session:
        resource = session.get(Resource, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        if resource.type != "comic":
            raise HTTPException(status_code=400, detail="Resource is not a comic")
        
        # 验证所有文件都属于这个资源
        file_ids = {item["id"] for item in payload.file_orders}
        files = session.query(ComicFile).filter(
            ComicFile.id.in_(file_ids),
            ComicFile.resource_id == resource_id
        ).all()
        
        if len(files) != len(file_ids):
            raise HTTPException(status_code=400, detail="部分文件ID不存在或不属于该资源")
        
        # 创建ID到文件的映射
        file_map = {file.id: file for file in files}
        
        # 更新顺序
        for item in payload.file_orders:
            file_id = item.get("id")
            order = item.get("order")
            if file_id in file_map:
                file_map[file_id].order = order
        
        session.flush()


@app.get("/settings", response_model=SettingsResponse)
async def get_settings(_: Annotated[str, Depends(require_admin)]):
    return SettingsResponse(
        page_size=settings.bot.page_size,
        search_channel_id=settings.channels.search_channel_id,
        comic_preview_channel_id=settings.channels.comic_preview_channel_id,
        storage_channel_id=settings.channels.storage_channel_id,
    )


@app.get("/users", response_model=List[UserResponse])
async def list_users(
    _: Annotated[str, Depends(require_admin)],
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    with db_session() as session:
        query = session.query(User)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.first_name.ilike(search_term))
                | (User.username.ilike(search_term))
                | (User.user_id.cast(String).ilike(search_term))
            )
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return [
        UserResponse(
            user_id=u.user_id,
            first_name=u.first_name,
            username=u.username,
            vip_expiry=u.vip_expiry,
            is_blocked=u.is_blocked,
            usage_quota=u.usage_quota,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


@app.get("/users/count")
async def get_users_count(
    _: Annotated[str, Depends(require_admin)],
    search: Optional[str] = Query(None),
):
    with db_session() as session:
        query = session.query(User)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.first_name.ilike(search_term))
                | (User.username.ilike(search_term))
                | (User.user_id.cast(String).ilike(search_term))
            )
        count = query.count()
    return {"count": count}


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            user_id=user.user_id,
            first_name=user.first_name,
            username=user.username,
            vip_expiry=user.vip_expiry,
            is_blocked=user.is_blocked,
            usage_quota=user.usage_quota,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


@app.post("/users", response_model=UserResponse)
async def create_user(
    payload: UserCreateIn,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        existing = session.get(User, payload.user_id)
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")
        user = User(
            user_id=payload.user_id,
            first_name=payload.first_name,
            username=payload.username,
            vip_expiry=payload.vip_expiry,
            is_blocked=payload.is_blocked,
        )
        session.add(user)
        session.flush()
        return UserResponse(
            user_id=user.user_id,
            first_name=user.first_name,
            username=user.username,
            vip_expiry=user.vip_expiry,
            is_blocked=user.is_blocked,
            usage_quota=user.usage_quota,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateIn,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if payload.first_name is not None:
            user.first_name = payload.first_name
        if payload.username is not None:
            user.username = payload.username
        if payload.vip_expiry is not None or "vip_expiry" in fields_set:
            user.vip_expiry = payload.vip_expiry
        if payload.is_blocked is not None:
            user.is_blocked = payload.is_blocked
        session.flush()
        return UserResponse(
            user_id=user.user_id,
            first_name=user.first_name,
            username=user.username,
            vip_expiry=user.vip_expiry,
            is_blocked=user.is_blocked,
            usage_quota=user.usage_quota,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


@app.delete("/users/{user_id}", status_code=204, response_class=Response)
async def delete_user(
    user_id: int,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        session.flush()
    return Response(status_code=204)


@app.post("/users/batch-delete", status_code=204, response_class=Response)
async def batch_delete_users(
    user_ids: Annotated[List[int], Body()],
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        users = session.query(User).filter(User.user_id.in_(user_ids)).all()
        for user in users:
            session.delete(user)
        session.flush()
    return Response(status_code=204)


# ==================== VIP 套餐管理 ====================

@app.get("/vip-plans", response_model=List[VipPlanResponse])
async def list_vip_plans(_: Annotated[str, Depends(require_admin)]):
    with db_session() as session:
        plans = session.query(VipPlan).order_by(VipPlan.sort_order.asc(), VipPlan.id.asc()).all()
        return [
            VipPlanResponse(
                id=plan.id,
                name=plan.name,
                duration_days=plan.duration_days,
                price=plan.price,
                description=plan.description,
                is_active=plan.is_active,
                sort_order=plan.sort_order,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
            for plan in plans
        ]


@app.post("/vip-plans", response_model=VipPlanResponse)
async def create_vip_plan(
    payload: VipPlanCreateIn,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        plan = VipPlan(
            name=payload.name,
            duration_days=payload.duration_days,
            price=payload.price,
            description=payload.description,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
        )
        session.add(plan)
        session.flush()
        return VipPlanResponse(
            id=plan.id,
            name=plan.name,
            duration_days=plan.duration_days,
            price=plan.price,
            description=plan.description,
            is_active=plan.is_active,
            sort_order=plan.sort_order,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


@app.put("/vip-plans/{plan_id}", response_model=VipPlanResponse)
async def update_vip_plan(
    plan_id: int,
    payload: VipPlanUpdateIn,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        plan = session.get(VipPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="VIP plan not found")
        fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
        if payload.name is not None:
            plan.name = payload.name
        if payload.duration_days is not None:
            plan.duration_days = payload.duration_days
        if payload.price is not None:
            plan.price = payload.price
        if payload.description is not None or "description" in fields_set:
            plan.description = payload.description
        if payload.is_active is not None:
            plan.is_active = payload.is_active
        if payload.sort_order is not None:
            plan.sort_order = payload.sort_order
        session.flush()
        return VipPlanResponse(
            id=plan.id,
            name=plan.name,
            duration_days=plan.duration_days,
            price=plan.price,
            description=plan.description,
            is_active=plan.is_active,
            sort_order=plan.sort_order,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


@app.delete("/vip-plans/{plan_id}", status_code=204, response_class=Response)
async def delete_vip_plan(
    plan_id: int,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        plan = session.get(VipPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="VIP plan not found")
        session.delete(plan)
        session.flush()
    return Response(status_code=204)


# ==================== 支付配置管理 ====================

@app.get("/payment-configs", response_model=List[PaymentConfigResponse])
async def list_payment_configs(_: Annotated[str, Depends(require_admin)]):
    with db_session() as session:
        configs = session.query(PaymentConfig).order_by(PaymentConfig.sort_order.asc(), PaymentConfig.id.asc()).all()
        return [
            PaymentConfigResponse(
                id=config.id,
                payment_type=config.payment_type,
                account_name=config.account_name,
                account_number=config.account_number,
                qr_code_url=config.qr_code_url,
                qr_code_file_id=config.qr_code_file_id,
                is_active=config.is_active,
                sort_order=config.sort_order,
                created_at=config.created_at,
                updated_at=config.updated_at,
            )
            for config in configs
        ]


@app.post("/payment-configs", response_model=PaymentConfigResponse)
async def create_payment_config(
    payload: PaymentConfigCreateIn,
    _: Annotated[str, Depends(require_admin)],
):
    if payload.payment_type not in ("wechat", "alipay"):
        raise HTTPException(status_code=400, detail="payment_type must be 'wechat' or 'alipay'")
    with db_session() as session:
        config = PaymentConfig(
            payment_type=payload.payment_type,
            account_name=payload.account_name,
            account_number=payload.account_number,
            qr_code_url=payload.qr_code_url,
            qr_code_file_id=payload.qr_code_file_id,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
        )
        session.add(config)
        session.flush()
        return PaymentConfigResponse(
            id=config.id,
            payment_type=config.payment_type,
            account_name=config.account_name,
            account_number=config.account_number,
            qr_code_url=config.qr_code_url,
            qr_code_file_id=config.qr_code_file_id,
            is_active=config.is_active,
            sort_order=config.sort_order,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


@app.put("/payment-configs/{config_id}", response_model=PaymentConfigResponse)
async def update_payment_config(
    config_id: int,
    payload: PaymentConfigUpdateIn,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        config = session.get(PaymentConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Payment config not found")
        fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
        if payload.account_name is not None or "account_name" in fields_set:
            config.account_name = payload.account_name
        if payload.account_number is not None or "account_number" in fields_set:
            config.account_number = payload.account_number
        if payload.qr_code_url is not None or "qr_code_url" in fields_set:
            config.qr_code_url = payload.qr_code_url
        if payload.qr_code_file_id is not None or "qr_code_file_id" in fields_set:
            config.qr_code_file_id = payload.qr_code_file_id
        if payload.is_active is not None:
            config.is_active = payload.is_active
        if payload.sort_order is not None:
            config.sort_order = payload.sort_order
        session.flush()
        return PaymentConfigResponse(
            id=config.id,
            payment_type=config.payment_type,
            account_name=config.account_name,
            account_number=config.account_number,
            qr_code_url=config.qr_code_url,
            qr_code_file_id=config.qr_code_file_id,
            is_active=config.is_active,
            sort_order=config.sort_order,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


@app.delete("/payment-configs/{config_id}", status_code=204, response_class=Response)
async def delete_payment_config(
    config_id: int,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        config = session.get(PaymentConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Payment config not found")
        session.delete(config)
        session.flush()
    return Response(status_code=204)


# ==================== 公开的支付信息接口（供机器人使用）====================

@app.get("/vip/payment-info", response_model=VipPaymentInfoResponse)
async def get_vip_payment_info():
    """获取 VIP 支付信息（公开接口，供机器人使用）"""
    with db_session() as session:
        # 获取所有启用的 VIP 套餐
        plans = (
            session.query(VipPlan)
            .filter(VipPlan.is_active == True)
            .order_by(VipPlan.sort_order.asc(), VipPlan.id.asc())
            .all()
        )
        plan_responses = [
            VipPlanResponse(
                id=plan.id,
                name=plan.name,
                duration_days=plan.duration_days,
                price=plan.price,
                description=plan.description,
                is_active=plan.is_active,
                sort_order=plan.sort_order,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
            for plan in plans
        ]
        
        # 获取启用的支付配置
        wechat_config = (
            session.query(PaymentConfig)
            .filter(PaymentConfig.payment_type == "wechat", PaymentConfig.is_active == True)
            .order_by(PaymentConfig.sort_order.asc())
            .first()
        )
        alipay_config = (
            session.query(PaymentConfig)
            .filter(PaymentConfig.payment_type == "alipay", PaymentConfig.is_active == True)
            .order_by(PaymentConfig.sort_order.asc())
            .first()
        )
        
        wechat_response = None
        if wechat_config:
            wechat_response = PaymentConfigResponse(
                id=wechat_config.id,
                payment_type=wechat_config.payment_type,
                account_name=wechat_config.account_name,
                account_number=wechat_config.account_number,
                qr_code_url=wechat_config.qr_code_url,
                qr_code_file_id=wechat_config.qr_code_file_id,
                is_active=wechat_config.is_active,
                sort_order=wechat_config.sort_order,
                created_at=wechat_config.created_at,
                updated_at=wechat_config.updated_at,
            )
        
        alipay_response = None
        if alipay_config:
            alipay_response = PaymentConfigResponse(
                id=alipay_config.id,
                payment_type=alipay_config.payment_type,
                account_name=alipay_config.account_name,
                account_number=alipay_config.account_number,
                qr_code_url=alipay_config.qr_code_url,
                qr_code_file_id=alipay_config.qr_code_file_id,
                is_active=alipay_config.is_active,
                sort_order=alipay_config.sort_order,
                created_at=alipay_config.created_at,
                updated_at=alipay_config.updated_at,
            )
        
        return VipPaymentInfoResponse(
            plans=plan_responses,
            wechat_config=wechat_response,
            alipay_config=alipay_response,
        )

