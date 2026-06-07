import json
from channels.generic.websocket import AsyncWebsocketConsumer


class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.dataset_id = self.scope['url_route']['kwargs']['dataset_id']
        self.group_name = f'dataset_{self.dataset_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def progress_update(self, event):
        await self.send(text_data=json.dumps({
            'progress': event['progress'],
            'status': event['status'],
            'message': event.get('message', ''),
        }))
