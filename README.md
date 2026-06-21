# AI 驱动的数据处理平台

Django + Celery + LangChain 构建的数据处理平台。用户上传 CSV/Excel，用自然语言查数据，AI 自动生成 SQL 并执行返回结果。

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-green)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)](https://vuejs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 功能特性

- **数据集管理**：上传 CSV/Excel 文件，异步解析入库，WebSocket 实时推送处理进度
- **自然语言查询**：AI 自动将中文问题转为 SQL 并执行（NL2SQL）
- **数据分析**：自动统计每列类型、空值、分布、高频值等
- **数据导出**：查询结果导出为 CSV / Excel
- **RBAC 权限**：admin / analyst / viewer 三角色，行级数据隔离
- **幂等上传**：Redis 分布式锁 + 数据库查重 + 数据库唯一约束，三道防线防重复
- **Celery 任务可靠性**：指数退避重试 + 死信队列
- **WebSocket 实时进度**：替代 HTTP 轮询，Celery 任务每处理 1 万行推送一次进度
- **NL2SQL 安全**：三层 SQL 安全校验（白名单 → 关键字拦截 → 注入拦截）

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端 | Python 3.12, Django 5.1, DRF 3.14, Celery 5.3, Channels |
| 数据库 | PostgreSQL 15, Redis 7 |
| AI/LLM | LangChain, 智谱 GLM (OpenAI 兼容 API) |
| 前端 | Vue 3.4, TypeScript, Element Plus 2.9, Pinia, Vue Router 4, Vite |
| 部署 | Docker Compose, Nginx, Daphne |

## 快速开始

### Docker Compose 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/x7atttt/AI-driven-data-processing-platform.git
cd AI-driven-data-processing-platform

# 2. 创建 .env.production 并填入真实值
cp .env.production .env.production
# 编辑 DJANGO_SECRET_KEY、DB_PASSWORD、OPENAI_API_KEY、ALLOWED_HOSTS 等

# 3. 构建并启动
docker compose --env-file .env.production up -d --build

# 4. 创建管理员账号
docker compose exec -it django python manage.py createsuperuser

# 5. 设置管理员角色
docker compose exec django python manage.py shell -c "
from apps.users.models import User
u = User.objects.first()
u.role = 'admin'
u.save()
"

# 6. 访问 http://你的服务器IP
```

### 本地开发

> ⚠️ 后端**必须**用 `daphne` 启动（不能用 `runserver`），因为 `runserver` 是 WSGI，不支持 WebSocket。

```bash
# 后端（HTTP + WebSocket，必须用 daphne）
pip install -r requirements.txt
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Celery（Windows 必须用 --pool=solo，prefork 不支持）
celery -A config worker -l info --pool=solo
celery -A config beat -l info

# 前端
cd frontend
npm install --legacy-peer-deps
npm run dev    # http://localhost:5173
```

> ⚠️ **必须同时启动 3 个终端**：daphne（HTTP + WS）+ celery worker（异步任务）+ vite dev（前端）。少起任何一个都会导致功能异常。

## 架构图

```
                    ┌─────────────┐
                    │   Nginx     │ :80
                    │  (前端)      │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │ /          │ /api/*     │ /ws/*
              ▼            ▼            ▼
        Vue3 SPA     ┌─────────────────────┐
        (dist)       │  Django (Daphne)    │ :8000
                      │  DRF + Channels     │
                      └──┬──────┬──────┬───┘
                         │      │      │
                    ┌────▼┐ ┌──▼──┐ ┌─▼──────┐
                    │ PG  │ │Redis│ │ Celery  │
                    │ :5432│ │:6379│ │ Worker  │
                    └─────┘ └─────┘ │ + Beat  │
                                     └─────────┘
```

## 项目结构

```
├── config/                  # Django 配置、URL、Celery、ASGI
├── apps/
│   ├── users/               # 用户模型、RBAC、认证 API
│   ├── datasets/            # 上传、解析、Celery 任务、分析器
│   ├── query/               # NL2SQL 服务、查询 API
│   └── export/              # CSV/Excel 导出
├── frontend/                # Vue 3 + TypeScript + Element Plus
│   ├── src/views/           # 7 个页面
│   ├── src/styles/          # CSS 主题系统
│   ├── src/components/      # 公共组件
│   └── Dockerfile           # 多阶段构建（Node → Nginx）
├── nginx/
│   └── nginx.conf           # 反向代理配置
├── docker-compose.yml       # 6 个服务
├── Dockerfile               # 后端镜像
└── requirements.txt         # Python 依赖
```

## API 接口概览

| 接口 | 方法 | 描述 | 权限 |
|------|------|------|------|
| `/api/users/register/` | POST | 注册 | 公开 |
| `/api/users/login/` | POST | 登录 | 公开 |
| `/api/users/logout/` | POST | 注销 | 需登录 |
| `/api/users/profile/` | GET | 当前用户信息 | 需登录 |
| `/api/users/manage/` | GET | 用户列表 | 管理员 |
| `/api/users/manage/{id}/` | PATCH/DELETE | 改角色 / 禁用 | 管理员 |
| `/api/datasets/` | GET/POST | 列表 / 上传 | 上传：Analyst+ |
| `/api/datasets/{id}/` | GET/DELETE | 详情 / 删除 | 删除：Analyst+ |
| `/api/datasets/{id}/analysis/` | GET | 列统计 | 需登录 |
| `/api/query/{dataset_id}/` | POST | 自然语言查询 | 需登录 |
| `/api/query/history/` | GET | 查询历史 | 需登录 |
| `/api/export/{query_id}/csv/` | GET | 导出 CSV | Analyst+ |
| `/api/export/{query_id}/xlsx/` | GET | 导出 Excel | Analyst+ |

### WebSocket 接口

| 接口 | 描述 | 认证 |
|------|------|------|
| `/ws/datasets/{dataset_id}/progress/` | 数据集处理进度实时推送 | Session（Cookie） |

**消息格式**（服务端 → 客户端，JSON）：

```json
{
  "progress": 30000,
  "status": "processing",
  "message": "已处理 30000 行"
}
```

`status` 取值：`processing`（处理中）| `completed`（完成）| `failed`（失败，终态后客户端主动关闭连接）

## RBAC 权限矩阵

| 功能 | Admin | Analyst | Viewer |
|------|:-----:|:-------:|:------:|
| 上传数据集 | ✅ | ✅ | ❌ |
| 删除数据集 | ✅ | ✅ | ❌ |
| 查询（NL2SQL） | ✅ | ✅ | ✅ |
| 导出数据 | ✅ | ✅ | ❌ |
| 管理用户 | ✅ | ❌ | ❌ |

所有查询结果通过 `owner=request.user` 过滤，实现行级数据隔离。

## 关键设计决策

- **幂等上传**：Redis SETNX 锁 + 数据库 `(owner, file_md5)` 唯一约束
- **Celery 可靠性**：`acks_late=True`、指数退避重试（最多 5 次）、失败入死信队列
- **NL2SQL 流水线**：7 步工作流 + 三层 SQL 安全校验，失败自动重试（最多 3 次），自动加 LIMIT 1000
- **前端主题**：CSS 自定义属性 + Element Plus 变量覆盖，零额外依赖

## 环境变量

| 变量 | 必填 | 说明 |
|------|:----:|------|
| `DJANGO_SECRET_KEY` | 是 | 随机密钥 |
| `DJANGO_DEBUG` | 是 | `True` / `False` |
| `DB_HOST` | 是 | `db`（Docker）/ `localhost`（本地） |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | 是 | PostgreSQL 凭证 |
| `REDIS_URL` | 是 | `redis://redis:6379/1`（Docker） |
| `OPENAI_API_KEY` | 是 | 智谱 API key |
| `OPENAI_API_BASE` | 是 | `https://open.bigmodel.cn/api/paas/v4` |
| `LLM_MODEL` | 否 | 默认：`GLM-4-Flash` |
| `ALLOWED_HOSTS` | 是 | 逗号分隔的域名列表 |

## License

MIT
