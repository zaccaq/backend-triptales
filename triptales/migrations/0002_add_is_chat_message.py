# triptales/migrations/0002_add_is_chat_message.py (esempio)
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('triptales', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='diarypost',
            name='is_chat_message',
            field=models.BooleanField(default=False),
        ),
    ]