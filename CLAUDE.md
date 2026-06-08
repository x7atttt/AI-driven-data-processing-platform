# CLAUDE.md — AI驱动的数据处理平台

## 项目概述

Django + Celery + LangChain 构建的数据处理平台。用户上传 CSV/Excel，用自然语言查数据，AI 自动生成 SQL 并执行返回结果。核心展示后端工程化能力：RBAC 权限、幂等上传、Celery 任务可靠性、批量写入优化。

## 技术栈

- **Web**: Django 4.2 + DRF 3.14
- **数据库**: PostgreSQL 15
- **异步任务**: Celery 5.3 + Redis 7
- **数据处理**: Pandas 2.2
- **AI/NL2SQL**: LangChain + langchain-openai（验证+自动重试）
- **前端**: Vue3 + Element Plus
- **部署**: Docker + Docker Compose

## 目录结构

```
data-platform/
├── config/                  # Django项目配置 (settings, urls, celery, asgi)
├── apps/
│   ├── users/               # 用户管理 + RBAC权限
│   │   ├── permissions.py   # IsAdmin / IsAnalyst / IsViewer
│   │   └── api/             # 注册/登录/用户管理接口
│   ├── datasets/            # 数据集管理
│   │   ├── services/
│   │   │   ├── parser.py    # Pandas文件解析 + bulk_create批量写入
│   │   │   ├── analyzer.py  # 数据分析
│   │   │   └── upload_lock.py # MD5去重 + Redis分布式锁
│   │   ├── tasks.py         # Celery异步任务 (指数退避重试+死信队列)
│   │   └── consumers.py     # WebSocket进度推送
│   ├── query/               # NL2SQL查询
│   │   └── services/nl2sql.py # LangChain NL2SQL Agent (Schema发现+SQL验证+自动重试)
│   └── export/              # 数据导出 (CSV/Excel)
├── frontend/                # Vue3前端
├── manage.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 关键架构决策

### RBAC 权限模型
- `admin`: 全权限 + 用户管理
- `analyst`: 上传 + 查询 + 导出
- `viewer`: 仅查询
- 自定义权限类在 `apps/users/permissions.py`，按 action 动态分配

### 幂等上传设计
- 双重保障：Redis SETNX 分布式锁（第一道） + 数据库 `file_md5` 唯一约束（第二道）
- 锁超时 5 分钟，防止死锁
- 小文件 (<10MB) 同步处理，大文件 (>=10MB) Celery 异步处理

### Celery 任务可靠性
- `acks_late=True`：任务完成后才确认，防止中途丢失
- 指数退避重试：2^n 秒 (1→2→4→8→16)，最多 5 次
- 超过重试上限标记 `failed`（死信队列），Admin 后台可见
- `--max-tasks-per-child=100`：防止内存泄漏

### NL2SQL Agent 设计
- 7步工作流：Schema发现 → Schema检查 → SQL生成 → SQL验证 → SQL执行 → 失败重试 → 结果格式化
- SQL 安全审查三层防护：白名单(仅SELECT) → 危险关键字拦截 → 禁止多语句(分号注入)
- Schema发现：获取表结构 + 3条样本行，帮助LLM理解数据格式
- 自动重试：SQL执行失败后，将错误信息反馈LLM自动重写SQL，最多重试3次
- 重试时再次安全审查，防止修复后的SQL包含危险操作
- 所有查询自动加 LIMIT 1000
- `temperature=0`：SQL 生成零温度保证稳定性

### 数据写入优化
- `bulk_create` 批量写入，batch_size=1000
- 对比逐条 save 有 ~100 倍性能差距
- Pandas 分块读取控制内存峰值 200MB 内

## 常用命令

```bash
# 启动开发
python manage.py runserver

# 数据库迁移
python manage.py makemigrations && python manage.py migrate

# Celery Worker
celery -A config worker -l info --concurrency=2 --max-tasks-per-child=100

# Celery Beat (定时任务)
celery -A config beat -l info

# 前端
cd frontend && npm run dev

# Docker 部署
docker-compose up -d
docker-compose exec django python manage.py migrate
docker-compose exec django python manage.py createsuperuser
```

## 开发约定

- 自定义 User 模型：`AUTH_USER_MODEL = 'users.User'`，不要用 Django 默认 User
- 数据隔离：所有 queryset 必须 `filter(owner=request.user)` 实现行级隔离
- 数据库索引：`datasets` 表 `(owner, created_at)`，`dataset_rows` 表 `(dataset, row_index)`
- 所有 app 在 `apps/` 目录下，已注册到 `INSTALLED_APPS`
- API 路由前缀：`/api/users/`, `/api/datasets/`, `/api/query/`, `/api/export/`

## 环境变量

- `DJANGO_SECRET_KEY`: Django 密钥
- `DJANGO_DEBUG`: 调试模式 (生产环境 False)
- `DATABASE_URL`: PostgreSQL 连接串
- `REDIS_URL`: Redis 连接串 (`redis://localhost:6379/1`)
- `OPENAI_API_KEY`: 智谱 API 密钥
- `OPENAI_API_BASE`: 智谱 API 地址 (`https://open.bigmodel.cn/api/paas/v4`)
- `LLM_MODEL`: 使用的模型名称 (默认 `GLM-4-Flash`)

## 检查清单

开发完成后需验证的关键项：
- RBAC 三角色权限正确
- 行级数据隔离：用户 A 看不到用户 B 的数据集
- 幂等上传：相同文件重复上传返回 409
- Redis 分布式锁 + 5 分钟过期
- Celery 指数退避重试 + 死信队列
- bulk_create 批量写入
- SQL 安全审查：DROP/DELETE 拦截、分号注入拦截
- 自动 LIMIT
- Schema发现：表结构 + 样本行
- SQL自动重试：LLM根据错误信息修复SQL，最多3次
- 复合索引 EXPLAIN 确认
