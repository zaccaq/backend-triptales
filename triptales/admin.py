from django.contrib import admin
from .models import Utente, Gruppo, GroupMembership, DiaryPost, PostMedia, Comment, Like, Badge, UserBadge

# Registra i modelli nell'admin
admin.site.register(Utente)
admin.site.register(Gruppo)
admin.site.register(GroupMembership)
admin.site.register(DiaryPost)
admin.site.register(PostMedia)
admin.site.register(Comment)
admin.site.register(Like)
admin.site.register(Badge)
admin.site.register(UserBadge)