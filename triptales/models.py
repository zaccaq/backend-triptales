from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone





class Utente(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    registration_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.username


class Gruppo(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    cover_image = models.ImageField(upload_to='group_covers/', null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=255)
    created_by = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(default=timezone.now)
    is_private = models.BooleanField(default=False)  # Campo aggiunto

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]

    user = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='memberships')
    group = models.ForeignKey(Gruppo, on_delete=models.CASCADE, related_name='memberships')
    join_date = models.DateTimeField(default=timezone.now)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.username} in {self.group.name} as {self.role}"


class DiaryPost(models.Model):
    group = models.ForeignKey(Gruppo, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    is_chat_message = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']  # Ordina per data di creazione

    def __str__(self):
        return self.title


class PostMedia(models.Model):
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    post = models.ForeignKey(DiaryPost, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')
    media_url = models.FileField(upload_to='post_media/')
    created_at = models.DateTimeField(default=timezone.now)
    detected_objects = models.JSONField(null=True, blank=True)
    ocr_text = models.TextField(null=True, blank=True)
    caption = models.TextField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.media_type} for {self.post.title}"


class Comment(models.Model):
    post = models.ForeignKey(DiaryPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"


class Like(models.Model):
    post = models.ForeignKey(DiaryPost, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"Like by {self.user.username} on {self.post.title}"


class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon_url = models.ImageField(upload_to='badge_icons/')
    criteria = models.JSONField()

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='users')
    earned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"


# Aggiungi questo al file triptales/models.py

class GroupInvite(models.Model):
    INVITE_STATUS = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    group = models.ForeignKey(Gruppo, on_delete=models.CASCADE, related_name='invites')
    invited_by = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='sent_invites')
    invited_user = models.ForeignKey(Utente, on_delete=models.CASCADE, related_name='received_invites')
    status = models.CharField(max_length=10, choices=INVITE_STATUS, default='pending')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('group', 'invited_user')

    def __str__(self):
        return f"Invite for {self.invited_user.username} to {self.group.name}"