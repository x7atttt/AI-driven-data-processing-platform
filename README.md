# AI-Driven Data Processing Platform

Django + Celery + LangChain 构建的数据处理平台。用户上传 CSV/Excel，用自然语言查数据，AI 自动生成 SQL 并执行返回结果。

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-green)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)](https://vuejs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Features

- **数据集管理**：上传 CSV/Excel 文件，异步解析入库，支持状态轮询
- **自然语言查询**：AI 自动将中文问题转为 SQL 并执行（NL2SQL）
- **数据分析**：自动统计每列类型、空值、分布、高频值等
- **数据导出**：查询结果导出为 CSV / Excel
- **RBAC 权限**：admin / analyst / viewer 三角色，行级数据隔离
- **幂等上传**：Redis 分布式锁 + 数据库唯一约束，防并发重复
- **Celery 任务可靠性**：指数退避重试 + 死信队列
- **NL2SQL 安全**：三层 SQL 安全校验（白名单 → 关键字拦截 → 注入拦截）

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.12, Django 5.1, DRF 3.14, Celery 5.3, Channels |
| Database | PostgreSQL 15, Redis 7 |
| AI/LLM | LangChain, 智谱 GLM (OpenAI-compatible API) |
| Frontend | Vue 3.4, TypeScript, Element Plus 2.9, Pinia, Vue Router 4, Vite |
| Deployment | Docker Compose, Nginx, Daphne |

## Quick Start

### Docker Compose (Recommended)

```bash
# 1. Clone
git clone https://github.com/x7atttt/AI-driven-data-processing-platform.git
cd AI-driven-data-processing-platform

# 2. Create .env.production and fill in real values
cp .env.production .env.production
# Edit DJANGO_SECRET_KEY, DB_PASSWORD, OPENAI_API_KEY, ALLOWED_HOSTS, etc.

# 3. Build and start
docker compose --env-file .env.production up -d --build

# 4. Create admin user
docker compose exec -it django python manage.py createsuperuser

# 5. Set admin role
docker compose exec django python manage.py shell -c "
from apps.users.models import User
u = User.objects.first()
u.role = 'admin'
u.save()
"

# 6. Visit http://your-server-ip
```

### Local Development

```bash
# Backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Celery
celery -A config worker -l info --concurrency=2
celery -A config beat -l info

# Frontend
cd frontend
pnpm install
pnpm dev    # http://localhost:5173
```

## Architecture

```
                    ┌─────────────┐
                    │   Nginx     │ :80
                    │  (frontend) │
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

## Project Structure

```
├── config/                  # Django settings, URLs, Celery, ASGI
├── apps/
│   ├── users/               # User model, RBAC, auth API
│   ├── datasets/            # Upload, parser, Celery tasks, analyzer
│   ├── query/               # NL2SQL service, query API
│   └── export/              # CSV/Excel export
├── frontend/                # Vue 3 + TypeScript + Element Plus
│   ├── src/views/           # 7 pages
│   ├── src/styles/          # CSS theme system
│   ├── src/components/      # Shared components
│   └── Dockerfile           # Multi-stage build (Node → Nginx)
├── nginx/
│   └── nginx.conf           # Reverse proxy config
├── docker-compose.yml       # 6 services
├── Dockerfile               # Backend image
└── requirements.txt         # Python dependencies
```

## API Overview

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/users/register/` | POST | Register | Public |
| `/api/users/login/` | POST | Login | Public |
| `/api/users/logout/` | POST | Logout | Required |
| `/api/users/profile/` | GET | Current user | Required |
| `/api/users/manage/` | GET | User list | Admin |
| `/api/users/manage/{id}/` | PATCH/DELETE | Update role / Disable | Admin |
| `/api/datasets/` | GET/POST | List / Upload | Upload: Analyst+ |
| `/api/datasets/{id}/` | GET/DELETE | Detail / Delete | Delete: Analyst+ |
| `/api/datasets/{id}/analysis/` | GET | Column statistics | Required |
| `/api/query/{dataset_id}/` | POST | Natural language query | Required |
| `/api/query/history/` | GET | Query history | Required |
| `/api/export/{query_id}/csv/` | GET | Export CSV | Analyst+ |
| `/api/export/{query_id}/xlsx/` | GET | Export Excel | Analyst+ |

## RBAC

| Feature | Admin | Analyst | Viewer |
|---------|-------|---------|--------|
| Upload datasets | ✅ | ✅ | ❌ |
| Delete datasets | ✅ | ✅ | ❌ |
| Query (NL2SQL) | ✅ | ✅ | ✅ |
| Export data | ✅ | ✅ | ❌ |
| Manage users | ✅ | ❌ | ❌ |

All querysets are filtered by `owner=request.user` for row-level isolation.

## Key Design Decisions

- **Idempotent Upload**: Redis SETNX lock + DB `(owner, file_md5)` unique constraint
- **Celery Reliability**: `acks_late=True`, exponential backoff retry (max 5), dead letter on failure
- **NL2SQL Pipeline**: 7-step workflow with 3-layer SQL security, auto-retry on failure (max 3), automatic LIMIT 1000
- **Frontend Theme**: CSS custom properties + Element Plus variable overrides, zero additional dependencies

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes | Random secret key |
| `DJANGO_DEBUG` | Yes | `True` / `False` |
| `DB_HOST` | Yes | `db` (Docker) / `localhost` (local) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Yes | PostgreSQL credentials |
| `REDIS_URL` | Yes | `redis://redis:6379/1` (Docker) |
| `OPENAI_API_KEY` | Yes | 智谱 API key |
| `OPENAI_API_BASE` | Yes | `https://open.bigmodel.cn/api/paas/v4` |
| `LLM_MODEL` | No | Default: `GLM-4-Flash` |
| `ALLOWED_HOSTS` | Yes | Comma-separated host list |

## License

MIT
