"""性能测试专用配置

用法：
    DJANGO_SETTINGS_MODULE=config.settings_perf python test/perf/bench.py

设计原则：
- 继承 settings.py 的全部生产配置（DB/Redis/INSTALLED_APPS 等）
- 仅覆盖性能测试必要的几项：
  1. 放开上传大小限制（默认 2.5MB 会 413 拒绝大文件）
  2. Celery 改为 eager 模式（同步执行任务，免起 worker，测纯计算性能）
  3. Channels 关闭（避免 _send_progress 依赖 Redis channel layer）

不修改 settings.py，生产配置零影响。
"""
from .settings import *  # noqa: F401,F403

# 1. 放开上传大小限制（默认 DATA_UPLOAD_MAX_MEMORY_SIZE = 2.5MB）
#    测 50 万行 CSV 约 50-80MB，需放宽到 200MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 内存/临时盘切换点保持 2MB

# 2. Celery eager：任务在调用进程内同步执行，不经过 broker
#    - 免起 celery worker，单进程即可压测
#    - 异常直接抛出（便于定位失败），不被 Celery 重试机制吞掉
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# 3. Channels：性能测试不关心 WebSocket 进度推送，用 InMemory 替代 Redis
#    避免 channels-redis 连接异常干扰主流程（tasks._send_progress 已 try/except 兜底）
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}
