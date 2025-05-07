from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Utente, Gruppo, GroupMembership, DiaryPost, PostMedia, Comment, Like, Badge, UserBadge
from .serializers import (UserSerializer, TripGroupSerializer, GroupMembershipSerializer,
                          DiaryPostSerializer, PostMediaSerializer, CommentSerializer,
                          LikeSerializer, BadgeSerializer, UserBadgeSerializer)
from .permissions import IsOwnerOrReadOnly, IsMemberOrReadOnly, IsGroupAdmin

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')

        if not all([username, email, password, first_name, last_name]):
            return Response({"error": "Tutti i campi sono obbligatori."},
                           status=status.HTTP_400_BAD_REQUEST)

        if Utente.objects.filter(username=username).exists():
            return Response({"error": "Username già in uso."},
                           status=status.HTTP_400_BAD_REQUEST)

        if Utente.objects.filter(email=email).exists():
            return Response({"error": "Email già registrata."},
                           status=status.HTTP_400_BAD_REQUEST)

        try:
            user = Utente.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            user.save()

            return Response({"message": "Registrazione avvenuta con successo."},
                           status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Errore del server: {str(e)}"},
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserViewSet(viewsets.ModelViewSet):
    queryset = Utente.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            # Permette a chiunque di registrarsi (nessuna autenticazione richiesta)
            return [permissions.AllowAny()]
        # Per tutte le altre azioni, richiede l'autenticazione
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def groups(self, request, pk=None):
        user = self.get_object()
        memberships = GroupMembership.objects.filter(user=user)
        groups = [membership.group for membership in memberships]
        serializer = TripGroupSerializer(groups, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def badges(self, request, pk=None):
        user = self.get_object()
        user_badges = UserBadge.objects.filter(user=user)
        serializer = UserBadgeSerializer(user_badges, many=True)
        return Response(serializer.data)


class TripGroupViewSet(viewsets.ModelViewSet):
    queryset = Gruppo.objects.all()
    serializer_class = TripGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'location']

    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        # Auto-add creator as admin
        GroupMembership.objects.create(user=self.request.user, group=group, role='admin')

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        group = self.get_object()

        # Check if user is already a member
        if GroupMembership.objects.filter(user=request.user, group=group).exists():
            return Response({"detail": "You are already a member of this group."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Add user to group
        membership = GroupMembership.objects.create(
            user=request.user,
            group=group,
            role='member'
        )

        serializer = GroupMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        group = self.get_object()

        try:
            membership = GroupMembership.objects.get(user=request.user, group=group)

            # Check if user is the last admin
            if membership.role == 'admin':
                admin_count = GroupMembership.objects.filter(group=group, role='admin').count()
                if admin_count <= 1:
                    return Response({"detail": "Cannot leave group. You are the only admin."},
                                    status=status.HTTP_400_BAD_REQUEST)

            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except GroupMembership.DoesNotExist:
            return Response({"detail": "You are not a member of this group."},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        group = self.get_object()
        memberships = group.memberships.all()
        serializer = GroupMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def posts(self, request, pk=None):
        group = self.get_object()
        posts = DiaryPost.objects.filter(group=group).order_by('-created_at')
        serializer = DiaryPostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


class GroupMembershipViewSet(viewsets.ModelViewSet):
    queryset = GroupMembership.objects.all()
    serializer_class = GroupMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsGroupAdmin]

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        membership = self.get_object()

        # Check if user is admin of this group
        requester_is_admin = GroupMembership.objects.filter(
            user=request.user,
            group=membership.group,
            role='admin'
        ).exists()

        if not requester_is_admin:
            return Response({"detail": "Only admins can promote members."},
                            status=status.HTTP_403_FORBIDDEN)

        membership.role = 'admin'
        membership.save()

        serializer = self.get_serializer(membership)
        return Response(serializer.data)


class DiaryPostViewSet(viewsets.ModelViewSet):
    queryset = DiaryPost.objects.all()
    serializer_class = DiaryPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsMemberOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        post = self.get_object()

        # Check if already liked
        if Like.objects.filter(user=request.user, post=post).exists():
            return Response({"detail": "You've already liked this post."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create like
        like = Like.objects.create(user=request.user, post=post)
        serializer = LikeSerializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def unlike(self, request, pk=None):
        post = self.get_object()

        try:
            like = Like.objects.get(user=request.user, post=post)
            like.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Like.DoesNotExist:
            return Response({"detail": "You haven't liked this post."},
                            status=status.HTTP_400_BAD_REQUEST)


class PostMediaViewSet(viewsets.ModelViewSet):
    queryset = PostMedia.objects.all()
    serializer_class = PostMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class BadgeViewSet(viewsets.ModelViewSet):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserBadgeViewSet(viewsets.ModelViewSet):
    queryset = UserBadge.objects.all()
    serializer_class = UserBadgeSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def award_explorer_badge(self, request):
        # Logic to award Explorer badge
        # For example: User has created posts in 5+ different locations
        explorer_badge = get_object_or_404(Badge, name="Esploratore")

        user_post_locations = DiaryPost.objects.filter(
            author=request.user,
            location_name__isnull=False
        ).values('location_name').distinct().count()

        if user_post_locations >= 5 and not UserBadge.objects.filter(user=request.user, badge=explorer_badge).exists():
            user_badge = UserBadge.objects.create(
                user=request.user,
                badge=explorer_badge
            )
            serializer = self.get_serializer(user_badge)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response({"detail": "Requirements not met for Explorer badge."},
                        status=status.HTTP_400_BAD_REQUEST)