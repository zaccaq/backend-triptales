from django.contrib.auth.models import User
from django.db import models

class TripGroup(models.Model):
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(User, related_name='trip_groups')
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='posts/')
    description = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Badge(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    users = models.ManyToManyField(User, related_name='badges')
