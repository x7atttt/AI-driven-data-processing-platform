import json
from channels.generic.websocket import AsyncWebsocketConsumer


class ProgressConsumer(AsyncWebsocketConsumer):
    """数据集处理进度 WebSocket 推送

    前端连接 ws://host/ws/datasets/<dataset_id>/progress/ 后，
    Celery 任务通过 channel_layer.group_send() 推送进度，
    Consumer 将消息转发给前端。

    消息流：Celery task (同步进程)
      → channel_layer.group_send() (经 Redis 中转)
      → progress_update() (本 Consumer)
      → send() → 前端
    """

    async def connect(self):
        # scope 类似 HTTP request，包含 URL 路由参数
        self.dataset_id = self.scope['url_route']['kwargs']['dataset_id']
        # 每个数据集一个 group，实现隔离：只推送该数据集的进度
        self.group_name = f'dataset_{self.dataset_id}'

        # 加入 group，后续 group_send 的消息会路由到此连接
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # 离开 group，不再接收该数据集的进度消息
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

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
