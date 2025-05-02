from rest_framework import serializers
from .models import Utente, Gruppo, GroupMembership, DiaryPost, PostMedia, Comment, Like, Badge, UserBadge


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Utente
        fields = ['id', 'username', 'email', 'password', 'profile_picture', 'registration_date']

    def create(self, validated_data):
        user = Utente.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )

        # Se ci sono campi aggiuntivi da salvare
        if 'profile_picture' in validated_data:
            user.profile_picture = validated_data['profile_picture']

        user.save()
        return user


class TripGroupSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Gruppo
        fields = ['id', 'name', 'description', 'cover_image', 'start_date', 'end_date',
                  'location', 'created_by', 'created_at', 'member_count']

    def get_member_count(self, obj):
        return obj.memberships.count()


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = TripGroupSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'group', 'join_date', 'role']


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'content', 'created_at']


class LikeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'post', 'user', 'created_at']


class PostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostMedia
        fields = ['id', 'post', 'media_type', 'media_url', 'created_at',
                  'detected_objects', 'ocr_text', 'caption', 'latitude', 'longitude']


class DiaryPostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()

    class Meta:
        model = DiaryPost
        fields = ['id', 'group', 'author', 'title', 'content', 'created_at',
                  'latitude', 'longitude', 'location_name', 'comments', 'media',
                  'likes_count', 'user_has_liked']

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_user_has_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'name', 'description', 'icon_url', 'criteria']


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ['id', 'user', 'badge', 'earned_at']
