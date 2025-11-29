# Telegram Bot 搜索系统

一个基于 Telegram Bot 的资源搜索和管理系统，支持小说、音频和漫画资源的管理。

## 功能特性

- 📚 资源管理：支持小说、音频和漫画三种资源类型
- 🔍 智能搜索：通过 Telegram 频道进行资源搜索
- 👥 用户管理：完整的用户管理系统，支持 VIP 权限管理
- 🎨 管理面板：现代化的 Web 管理界面
- 📦 批量上传：支持批量上传压缩包并自动解压
- 🖼️ 图片管理：支持图片顺序调整和预览

## 环境要求

- Python 3.9+
- Node.js 18+
- pnpm
- MySQL 或 SQLite

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd SearchBot
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并填写配置：

```bash
cp env.example .env
```

编辑 `.env` 文件，配置以下内容：

```env
# Bot 配置
BOT_TOKEN=your_bot_token
BOT_USERNAME=your_bot_username

# 数据库配置
DATABASE_URL=sqlite:///./data.db
# 或使用 MySQL
# DATABASE_URL=mysql+pymysql://user:password@localhost/dbname

# 频道配置
SEARCH_CHANNEL_ID=-1001234567890
STORAGE_CHANNEL_ID=-1001234567890
COMIC_PREVIEW_CHANNEL_ID=-1001234567890

# VIP 充值链接
VIP_RECHARGE_URL=https://example.com/recharge

# 管理员配置
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_password
ADMIN_SECRET_KEY=your_secret_key

# 服务器配置（生产环境）
WEB_PORT=8000
NODE_ENV=production
SERVER_MODE=true
FORCE_SECURE_COOKIE=false  # 如果使用 HTTPS，设置为 true
```

### 3. 安装依赖

```bash
# 安装 Python 依赖
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 安装 Node.js 依赖
pnpm install
```

### 4. 配置前端环境变量

创建 `.env.local` 文件（用于 Next.js）：

```bash
# 后端 API 地址
# 本地开发
ADMIN_API_BASE_URL=http://127.0.0.1:8000
WEB_PORT=8000

# 服务器部署（根据实际情况修改）
# ADMIN_API_BASE_URL=http://127.0.0.1:8000
# 或如果后端在不同服务器
# ADMIN_API_BASE_URL=http://your-backend-server:8000
```

## 启动项目

### 方式一：使用启动脚本（推荐）

```bash
# 启动所有服务
./start.sh

# 停止所有服务
./stop.sh
```

### 方式二：手动启动

#### 启动后端服务

```bash
source .venv/bin/activate
uvicorn src.web:app --host 0.0.0.0 --port 8000 --reload
```

#### 启动机器人服务

```bash
source .venv/bin/activate
python -m src.bot
```

#### 启动前端服务

```bash
pnpm dev
```

## 服务器部署

### 1. 配置环境变量

在服务器上创建 `.env` 和 `.env.local` 文件，确保：

- `ADMIN_API_BASE_URL` 指向正确的后端地址
- 如果使用 HTTPS，设置 `FORCE_SECURE_COOKIE=true`
- 设置 `NODE_ENV=production` 和 `SERVER_MODE=true`

### 2. 使用 PM2 或 systemd 管理进程

#### 使用 PM2

```bash
# 安装 PM2
npm install -g pm2

# 启动后端
pm2 start "uvicorn src.web:app --host 0.0.0.0 --port 8000" --name backend

# 启动机器人
pm2 start "python -m src.bot" --name bot

# 启动前端（生产模式）
pm2 start "pnpm start" --name frontend
```

#### 使用 systemd

创建服务文件 `/etc/systemd/system/searchbot-backend.service`:

```ini
[Unit]
Description=SearchBot Backend
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SearchBot
Environment="PATH=/path/to/SearchBot/.venv/bin"
ExecStart=/path/to/SearchBot/.venv/bin/uvicorn src.web:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. 使用 Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 常见问题

### 1. 登录后立即退出

**问题**：登录成功但立即被退回，显示 401 Unauthorized

**解决方案**：
1. 检查 `.env.local` 中的 `ADMIN_API_BASE_URL` 是否正确
2. 确保后端服务正在运行
3. 如果使用 HTTPS，设置 `FORCE_SECURE_COOKIE=true`
4. 检查浏览器控制台是否有 Cookie 相关的错误

### 2. 机器人无法启动

**问题**：`TelegramConflictError: terminated by other getUpdates request`

**解决方案**：
- 确保只有一个机器人实例在运行
- 检查是否有其他进程占用了机器人

### 3. Cookie 无法保存

**问题**：登录后 Cookie 没有保存

**解决方案**：
- 检查 Cookie 的 `secure` 属性设置
- 如果使用 HTTPS，确保 `FORCE_SECURE_COOKIE=true`
- 检查浏览器的 Cookie 设置

## 开发

### 项目结构

```
SearchBot/
├── src/              # Python 后端代码
│   ├── bot.py       # Telegram Bot 主程序
│   ├── web.py       # FastAPI 后端 API
│   ├── db.py        # 数据库模型
│   └── ...
├── app/              # Next.js 前端代码
│   ├── api/         # API 路由
│   └── ...
├── components/       # React 组件
└── lib/             # 工具函数
```

### API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看 API 文档。

## 许可证

MIT License
