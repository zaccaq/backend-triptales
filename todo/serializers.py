from rest_framework import serializers
from .models import TripGroup, Post, Comment, Badge

class TripGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripGroup
        fields = '__all__'

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = '__all__'

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = '__all__'

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = '__all__'
