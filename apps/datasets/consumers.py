import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q


class ProgressConsumer(AsyncWebsocketConsumer):
    """数据集处理进度 WebSocket 推送

    前端连接 ws://host/ws/datasets/<dataset_id>/progress/ 后，
    Celery 任务通过 channel_layer.group_send() 推送进度，
    Consumer 将消息转发给前端。

    消息流：Celery task (同步进程)
      → channel_layer.group_send() (经 Redis 中转)
      → progress_update() (本 Consumer)
      → send() → 前端

    连接鉴权：AuthMiddlewareStack 已把 session 解析成 scope['user']，
    这里校验 user 对该 dataset 的可见性（与 DatasetViewSet.get_queryset 一致）。
    匿名用户或无可见权限的连接直接关闭，避免任何人凭 UUID 订阅进度。
    """

    async def connect(self):
        # scope 类似 HTTP request，包含 URL 路由参数
        self.dataset_id = self.scope['url_route']['kwargs']['dataset_id']

        # 鉴权：校验用户登录 + 对该数据集可见
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            # 未登录，关闭连接（code 4001 = 自定义未认证）
            await self.close(code=4001)
            return

        if not await self._user_can_access(user, self.dataset_id):
            # 登录了但对该数据集无可见权限，关闭（code 4003 = 自定义无权限）
            await self.close(code=4003)
            return

        # 每个数据集一个 group，实现隔离：只推送该数据集的进度
        self.group_name = f'dataset_{self.dataset_id}'

        # 加入 group，后续 group_send 的消息会路由到此连接
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _user_can_access(self, user, dataset_id: str) -> bool:
        """数据集可见性校验，与 DatasetViewSet.get_queryset 分层一致。

        admin 任意、analyst 自己 owner 的、viewer 被分享的。
        只判断"能不能看"，不涉及 action 权限（这里只是订阅进度，不是上传/删除）。
        """
        from apps.datasets.models import Dataset
        if user.is_admin:
            return Dataset.objects.filter(id=dataset_id).exists()
        if user.is_analyst:
            return Dataset.objects.filter(id=dataset_id, owner=user).exists()
        # viewer：被分享的 或 自己 owner 的（viewer 理论上不能上传，但兜底）
        return Dataset.objects.filter(
            Q(owner=user) | Q(shares__shared_to=user)
        ).filter(id=dataset_id).distinct().exists()

    async def disconnect(self, close_code):
        # 离开 group，不再接收该数据集的进度消息
        # 鉴权失败时 group_name 未设置，跳过 group_discard
        group_name = getattr(self, 'group_name', None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def progress_update(self, event):
        """处理 group_send 中 type="progress_update" 的消息

        方法名必须与 group_send 的 type 字段一致（点号变下划线）。
        event 结构: {"type": "progress_update", "progress": 50, "status": "processing", ...}
        """
        await self.send(text_data=json.dumps({
            'progress': event['progress'],
            'status': event['status'],
            'message': event.get('message', ''),
        }))
