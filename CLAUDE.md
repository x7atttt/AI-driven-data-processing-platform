# CLAUDE.md — AI驱动的数据处理平台

Django + Celery + LangChain 构建的数据处理平台。用户上传 CSV/Excel，用自然语言查数据，AI 自动生成 SQL 并执行返回结果。

详细设计文档见：`项目二开发指导文档.md`

## 技术栈

Django 4.2 / DRF 3.14 / PostgreSQL 15 / Redis 7 / Celery 5.3 / Pandas 2.2 / LangChain / Vue3 + Element Plus / Docker

## 目录结构

```
├── config/                  # Django项目配置 (settings, urls, celery, asgi)
├── apps/
│   ├── users/               # 用户管理 + RBAC权限
│   ├── datasets/            # 数据集管理 (上传/解析/异步任务/WebSocket)
│   ├── query/               # NL2SQL查询
│   └── export/              # 数据导出 (CSV/Excel)
├── frontend/                # Vue3前端
└── docker-compose.yml
```

## 开发约定

- 自定义 User 模型：`AUTH_USER_MODEL = 'users.User'`，不要用 Django 默认 User
- 数据隔离：所有 queryset 必须 `filter(owner=request.user)` 实现行级隔离
- 所有 app 在 `apps/` 目录下，已注册到 `INSTALLED_APPS`
- API 路由前缀：`/api/users/`, `/api/datasets/`, `/api/query/`, `/api/export/`
- 实现细节和架构决策见 `项目二开发指导文档.md`，本文档只放编码规则

## 常用命令

```bash
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
celery -A config worker -l info --concurrency=2 --max-tasks-per-child=100
celery -A config beat -l info
cd frontend && npm run dev
docker-compose up -d
```

## 环境变量

- `DJANGO_SECRET_KEY` / `DJANGO_DEBUG`
- `DATABASE_URL`: PostgreSQL 连接串
- `REDIS_URL`: Redis 连接串 (`redis://localhost:6379/1`)
- `OPENAI_API_KEY`: 智谱 API 密钥
- `OPENAI_API_BASE`: 智谱 API 地址 (`https://open.bigmodel.cn/api/paas/v4`)
- `LLM_MODEL`: 模型名称 (默认 `GLM-4-Flash`)
