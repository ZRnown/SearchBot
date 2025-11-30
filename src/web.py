from __future__ import annotations

import os
import zipfile
import tempfile
import shutil
from datetime import datetime, timedelta
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
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlalchemy import String

from .config import settings
from .db import AdminUser, ComicFile, Resource, SearchButton, User, db_session, init_db


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


logger = logging.getLogger(__name__)
MAX_BCRYPT_BYTES = 72
app = FastAPI(title="Resource Admin Panel")
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
    expire = datetime.utcnow() + (
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
):
    bot_username = await get_bot_username()
    with db_session() as session:
        query = session.query(Resource)
        if resource_type:
            query = query.filter(Resource.type == resource_type)
        resources = query.order_by(Resource.created_at.desc()).all()
    return [build_resource_response(res, bot_username) for res in resources]


@app.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    with db_session() as session:
        resource = session.get(Resource, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
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
            session.delete(resource)
        session.flush()
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

    # 发送前几张图片到预览频道
    preview_file_ids = stored_file_ids[:min(preview_count, len(stored_file_ids))]
    preview_messages = []
    for file_id in preview_file_ids:
        try:
            message = await admin_bot.send_photo(
                settings.channels.comic_preview_channel_id,
                photo=file_id,
            )
            preview_messages.append(message)
        except Exception as e:
            logger.error(f"发送预览图片失败: {e}")
            # 预览失败不影响主流程，继续执行

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
        # 如果有预览消息，使用第一个预览消息的链接
        if preview_messages:
            preview_msg_id = preview_messages[0].message_id
            formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
            resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
            
            # 在预览消息后发送一条带深度链接按钮的消息（回复到最后一个预览消息）
            try:
                last_preview_msg_id = preview_messages[-1].message_id
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=title, url=deep_link)
                ]])
                await admin_bot.send_message(
                    settings.channels.comic_preview_channel_id,
                    text=f"📖 {title}",
                    reply_to_message_id=last_preview_msg_id,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"发送深度链接按钮失败: {e}")
                # 按钮发送失败不影响主流程
        else:
            resource.preview_url = deep_link
        
        for order, file_id in enumerate(stored_file_ids, start=1):
            session.add(
                ComicFile(
                    resource_id=resource.id,
                    file_id=file_id,
                    order=order,
                )
            )

        session.flush()
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
                for member in zip_ref.namelist():
                    member_path = Path(member)
                    if member_path.suffix.lower() in image_extensions:
                        # 提取到临时目录
                        zip_ref.extract(member, extracted_dir)
                        full_path = Path(extracted_dir) / member_path
                        if full_path.exists() and full_path.is_file():
                            images.append(full_path)
        elif archive_type == 'rar' and RAR_SUPPORT:
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                for member in rar_ref.namelist():
                    member_path = Path(member)
                    if member_path.suffix.lower() in image_extensions:
                        # 提取到临时目录
                        rar_ref.extract(member, extracted_dir)
                        full_path = Path(extracted_dir) / member_path
                        if full_path.exists() and full_path.is_file():
                            images.append(full_path)
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
    
    # 保存压缩包到临时文件
    archive_content = await archive.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{archive_type}") as tmp_archive:
        tmp_archive.write(archive_content)
        tmp_archive_path = Path(tmp_archive.name)
    
    extracted_dir = None
    try:
        # 解压并提取图片
        image_files, extracted_dir = extract_images_from_archive(tmp_archive_path, archive_type)
        if not image_files:
            raise HTTPException(status_code=400, detail="压缩包中未找到图片文件")
        
        # 发送所有图片到存储频道（逐个发送获取 file_id）
        stored_file_ids: list[str] = []
        for img_path in image_files:
            try:
                with open(img_path, 'rb') as f:
                    img_content = f.read()
                buffer = BufferedInputFile(img_content, filename=img_path.name)
                message = await admin_bot.send_photo(
                    settings.channels.storage_channel_id,
                    photo=buffer,
                )
                if not message.photo:
                    raise HTTPException(status_code=500, detail=f"无法获取文件 ID: {img_path.name}")
                stored_file_ids.append(message.photo[-1].file_id)
            except Exception as e:
                logger.error(f"发送图片失败 {img_path.name}: {e}")
                raise HTTPException(status_code=500, detail=f"发送图片失败: {img_path.name}")
        
        # 发送前几张图片到预览频道（作为一条媒体组消息）
        preview_file_ids = stored_file_ids[:min(preview_count, len(stored_file_ids))]
        preview_messages = []
        if preview_file_ids:
            try:
                from aiogram.types import InputMediaPhoto
                media_group = [InputMediaPhoto(media=file_id) for file_id in preview_file_ids]
                messages = await admin_bot.send_media_group(
                    settings.channels.comic_preview_channel_id,
                    media=media_group,
                )
                preview_messages.extend(messages)
            except Exception as e:
                logger.error(f"发送预览图片失败: {e}")
                # 预览失败不影响主流程，继续执行
        
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
            # 如果有预览消息，使用第一个预览消息的链接
            if preview_messages:
                preview_msg_id = preview_messages[0].message_id
                formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
                resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
                
                # 在预览消息后发送一条带深度链接按钮的消息
                try:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=title, url=deep_link)
                    ]])
                    await admin_bot.send_message(
                        settings.channels.comic_preview_channel_id,
                        text=f"📖 {title}",
                        reply_to_message_id=preview_msg_id,
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.error(f"发送深度链接按钮失败: {e}")
                    # 按钮发送失败不影响主流程
            else:
                resource.preview_url = deep_link
            
            for order, file_id in enumerate(stored_file_ids, start=1):
                session.add(
                    ComicFile(
                        resource_id=resource.id,
                        file_id=file_id,
                        order=order,
                    )
                )
            
            session.flush()
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
    if not archives:
        raise HTTPException(status_code=400, detail="至少上传一个压缩包")
    
    results = []
    for archive in archives:
        if not archive.filename:
            continue
        
        # 判断压缩包类型
        filename_lower = archive.filename.lower()
        if filename_lower.endswith('.zip'):
            archive_type = 'zip'
        elif filename_lower.endswith('.rar'):
            if not RAR_SUPPORT:
                logger.warning(f"跳过 {archive.filename}: RAR 格式需要安装 rarfile 库")
                continue
            archive_type = 'rar'
        else:
            logger.warning(f"跳过 {archive.filename}: 仅支持 zip 和 rar 格式")
            continue
        
        # 使用文件名（去掉扩展名）作为标题
        title = Path(archive.filename).stem
        
        # 保存压缩包到临时文件
        archive_content = await archive.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{archive_type}") as tmp_archive:
            tmp_archive.write(archive_content)
            tmp_archive_path = Path(tmp_archive.name)
        
        extracted_dir = None
        try:
            # 解压并提取图片
            image_files, extracted_dir = extract_images_from_archive(tmp_archive_path, archive_type)
            if not image_files:
                logger.warning(f"跳过 {archive.filename}: 压缩包中未找到图片文件")
                continue
            
            # 发送所有图片到存储频道（逐个发送获取 file_id）
            stored_file_ids: list[str] = []
            for img_path in image_files:
                try:
                    with open(img_path, 'rb') as f:
                        img_content = f.read()
                    buffer = BufferedInputFile(img_content, filename=img_path.name)
                    message = await admin_bot.send_photo(
                        settings.channels.storage_channel_id,
                        photo=buffer,
                    )
                    if not message.photo:
                        raise HTTPException(status_code=500, detail=f"无法获取文件 ID: {img_path.name}")
                    stored_file_ids.append(message.photo[-1].file_id)
                except Exception as e:
                    logger.error(f"发送图片失败 {img_path.name}: {e}")
                    raise HTTPException(status_code=500, detail=f"发送图片失败: {img_path.name}")
            
            # 发送前几张图片到预览频道（作为一条媒体组消息）
            preview_file_ids = stored_file_ids[:min(preview_count, len(stored_file_ids))]
            preview_messages = []
            if preview_file_ids:
                try:
                    from aiogram.types import InputMediaPhoto
                    media_group = [InputMediaPhoto(media=file_id) for file_id in preview_file_ids]
                    messages = await admin_bot.send_media_group(
                        settings.channels.comic_preview_channel_id,
                        media=media_group,
                    )
                    preview_messages.extend(messages)
                except Exception as e:
                    logger.error(f"发送预览图片失败: {e}")
            
            cover_file_id = stored_file_ids[0]
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
                if preview_messages:
                    preview_msg_id = preview_messages[0].message_id
                    formatted_id = format_channel_id_for_link(settings.channels.comic_preview_channel_id)
                    resource.preview_url = f"https://t.me/c/{formatted_id}/{preview_msg_id}"
                    
                    # 在预览消息后发送一条带深度链接按钮的消息
                    try:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text=title, url=deep_link)
                        ]])
                        await admin_bot.send_message(
                            settings.channels.comic_preview_channel_id,
                            text=f"📖 {title}",
                            reply_to_message_id=preview_msg_id,
                            reply_markup=keyboard,
                        )
                    except Exception as e:
                        logger.error(f"发送深度链接按钮失败: {e}")
                        # 按钮发送失败不影响主流程
                else:
                    resource.preview_url = deep_link
                
                for order, file_id in enumerate(stored_file_ids, start=1):
                    session.add(
                        ComicFile(
                            resource_id=resource.id,
                            file_id=file_id,
                            order=order,
                        )
                    )
                
                session.flush()
                results.append(ComicUploadResponse(
                    id=resource.id,
                    pages=len(stored_file_ids),
                    deep_link=deep_link,
                    preview_link=resource.preview_url,
                ))
        except Exception as e:
            logger.error(f"处理压缩包 {archive.filename} 失败: {e}")
            # 继续处理下一个，不中断批量上传
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
    
    if not results:
        raise HTTPException(status_code=400, detail="没有成功上传任何压缩包")
    
    return results


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

