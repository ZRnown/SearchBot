作为 gpt-5.1-codex-high 模型驱动的AI，我在Cursor IDE中为您服务，随时准备协助您的编程和其他需求。

# Telegram 混合资源分发系统

该项目同时服务两种完全不同的内容形态：

- **小说 / 音频**：搜索后直接跳转指定频道消息，机器人只负责索引。
- **漫画**：由机器人全量托管 file_id，按 `sendMediaGroup` 分批发送，并结合 VIP 权限控制。

主流程：公开搜索频道输入关键词 → 机器人返回 HTML 结果列表 → 漫画项跳转至预览频道封面 → Deep Link 进入机器人 `/start comic_<uuid>` → 机器人校验权限并批量发图。

---

## 1. 环境变量

示例位于根目录 `env.example`：

```
BOT_TOKEN=your-bot-token
ADMIN_IDS=12345678,87654321
SEARCH_CHANNEL_ID=-1000000000000
COMIC_PREVIEW_CHANNEL_ID=-1000000000001
STORAGE_CHANNEL_ID=-1000000000002
COMIC_BATCH_SIZE=10
FREE_VIEW_LIMIT=20
PAGE_SIZE=5
DATABASE_URL=mysql+pymysql://searchbot:searchbot@localhost:3306/searchbot
WEB_PORT=8080
WEB_ADMIN_USER=admin
WEB_ADMIN_PASS=admin123
ADMIN_API_BASE_URL=http://127.0.0.1:8080
ADMIN_JWT_SECRET=change-me
ADMIN_TOKEN_EXPIRE_MINUTES=60
```

- `COMIC_BATCH_SIZE`：每次 `sendMediaGroup` 发送的图片数量（≤10）。
- `FREE_VIEW_LIMIT`：非 VIP 允许阅读的最大图片序号（例：20 表示只能看前 20 张）。
- `ADMIN_IDS`：搜索机器人允许的管理者，未来可扩展后台命令。
- `ADMIN_JWT_SECRET`：Web 管理后台使用的 JWT 签名密钥，务必改成强随机字符串。
- `DATABASE_URL`：默认指向 MySQL（推荐 `utf8mb4` 编码），若需切回 SQLite 请自行修改。

---

## 2. 数据库结构（SQLAlchemy）

| 表名 | 关键字段 | 说明 |
|------|----------|------|
| `resources` | `id (UUID)`, `title`, `type (novel|audio|comic)`, `jump_url`, `cover_file_id`, `preview_message_id`, `is_vip` | 统一的资源索引。小说/音频仅使用 `jump_url`，漫画存 `cover_file_id`+预览消息 ID。 |
| `comic_files` | `resource_id` (FK), `file_id`, `order` | 漫画图片的顺序表，机器人批量读取发送。 |
| `users` | `user_id`, `vip_expiry`, `is_blocked`, `usage_quota` | 记录 VIP 到期时间及使用配额。 |
| `searches` | `user_id`, `keyword`, `selected_filter`, `page_index` | 搜索日志，用于灰度统计。 |

SQLite 默认部署，生产可切至 PostgreSQL（保留 UUID 字符串实现）。

---

## 3. 机器人（`src/bot.py`）

- **搜索监听**：仅监听 `SEARCH_CHANNEL_ID`，按关键词 + 过滤标签（小说 / 音频 / 漫画 / 全部）分页检索，渲染 HTML 消息 + InlineKeyboard。
- **链接策略**：
  - 小说/音频：直接跳转 `resources.jump_url`（形如 `https://t.me/c/CHANNEL/MSG`）。
  - 漫画：跳转 `COMIC_PREVIEW_CHANNEL_ID` 中的封面消息。
- **漫画 Deep Link**：
  - `/start comic_<uuid>` 触发 `send_comic_page`。
  - 非 VIP 且请求超过 `FREE_VIEW_LIMIT`，立即拦截并提示充值。
  - 每次发送 `BATCH_SIZE` 张图（默认为 10），随后补发一条导航消息 `[⬅️ 上一页] [x / y 页] [下一页 ➡️]`，按钮通过回调拉取下一批。

---

## 4. 管理后台（`src/web.py` + FastAPI）

### 4.0 登录与会话

- 前端地址 `http://localhost:3000/login`，输入 `WEB_ADMIN_USER` / `WEB_ADMIN_PASS`。
- FastAPI 提供 `/auth/login`、`/auth/profile`、`/auth/change-password`，使用 JWT + HttpOnly Cookie，前端与 API 之间不会暴露明文密码。
- 设置页新增「账户安全」模块，可在线修改密码（最少 8 位），强制验证旧密码。

### 4.1 小说 / 音频录入

`POST /resources/indexed`

```json
{
  "title": "一拳超人 S1",
  "type": "novel",
  "jump_url": "https://t.me/c/123456/789",
  "is_vip": true
}
```

仅解析链接并入库，无需上传文件。

### 4.2 漫画上传

`POST /resources/comics`（`multipart/form-data`）：

- `title`: 标题
- `is_vip`: 是否 VIP
- `files[]`: 多张图片，按文件名顺序上传

后台逻辑：

1. 将每张图片发至 `STORAGE_CHANNEL_ID`，获取 `file_id` 并按顺序写入 `comic_files`。
2. 用首张图作为封面，在 `COMIC_PREVIEW_CHANNEL_ID` 发送「点击阅读」按钮（Deep Link 指向 `/start comic_<resource_id>`）。
3. 更新 `resources.cover_file_id` + `preview_message_id`。

---

## 5. 核心模块一览

```
src/
├── bot.py                # aiogram3 主入口，搜索 + 漫画阅读
├── web.py                # FastAPI 管理后台，录入/上传
├── config.py             # .env 解析、频道/BATCH/VIP 配置
├── db.py                 # SQLAlchemy 模型与 Session
├── repositories.py       # 资源/漫画文件查询封装
├── services/search_service.py # 搜索分页与统计
├── renderers.py          # HTML 模板渲染
├── keyboards.py          # 搜索过滤/翻页 + 漫画导航键盘
└── utils.py              # `chunk_list` 等工具
```

运行方式：

```bash
# 准备 MySQL
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS searchbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Python 服务
pip install -r requirements.txt
python -m src.bot
uvicorn src.web:app --reload --port $WEB_PORT

# Next.js 管理后台
pnpm install
pnpm dev  # http://localhost:3000
```

Next.js 通过 `/api/*` Route Handler 代理到 FastAPI，并将 JWT 保存在 HttpOnly Cookie（`admin_token`）里；若后端端口或域名不同，可通过 `ADMIN_API_BASE_URL` 覆盖。

---

## 6. 待办清单

- [ ] 接入支付/订单系统，为 VIP 充值提供真实链接。
- [ ] 为漫画导航消息增加历史删除逻辑，保持会话整洁。
- [ ] 增强上传校验（尺寸/格式）与重试机制。
- [ ] 添加单元测试（搜索分页、VIP 拦截、FastAPI 上传流程）。

# SearchBot
