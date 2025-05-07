# triptales/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Gruppo, DiaryPost, Utente


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.room_group_name = f'chat_{self.group_id}'

        # Verifica se l'utente è autenticato e membro del gruppo
        if self.scope['user'].is_anonymous:
            await self.close()
            return

        user_in_group = await self.is_user_in_group(self.scope['user'], self.group_id)
        if not user_in_group:
            await self.close()
            return

        # Unisciti al gruppo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Lascia il gruppo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'message')

        if message_type == 'message':
            message = text_data_json.get('message', '')
            user_id = self.scope['user'].id
            username = self.scope['user'].username

            # Salva il messaggio nel database
            await self.save_message(user_id, message)

            # Invia il messaggio al gruppo
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user_id': user_id,
                    'username': username,
                    'timestamp': timezone.now().isoformat()
                }
            )

        elif message_type == 'image':
            # Gestione delle immagini verrà implementata separatamente
            pass

    async def chat_message(self, event):
        # Invia il messaggio al WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def is_user_in_group(self, user, group_id):
        try:
            return user.memberships.filter(group__id=group_id).exists()
        except:
            return False

    @database_sync_to_async
    def save_message(self, user_id, message):
        try:
            user = Utente.objects.get(id=user_id)
            group = Gruppo.objects.get(id=self.group_id)
            DiaryPost.objects.create(
                group=group,
                author=user,
                title="Chat message",
                content=message,
                created_at=timezone.now()
            )
        except Exception as e:
            print(f"Error saving message: {e}")