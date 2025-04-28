from rest_framework import viewsets
from .models import TripGroup, Post, Comment, Badge
from .serializers import TripGroupSerializer, PostSerializer, CommentSerializer, BadgeSerializer

class TripGroupViewSet(viewsets.ModelViewSet):
    queryset = TripGroup.objects.all()
    serializer_class = TripGroupSerializer

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer

class CommentViewSet(viewsets.ModelViewSet):
    queryset = CommentSerializer

class BadgeViewSet(viewsets.ModelViewSet):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
