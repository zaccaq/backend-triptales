from rest_framework import viewsets, permissions, status, filters, parsers
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
from .badge_service import BadgeService

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

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Restituisce le statistiche dell'utente corrente."""
        user = request.user

        # Calcola le statistiche
        post_count = DiaryPost.objects.filter(author=user).count()

        # Likes ricevuti sui post dell'utente
        likes_count = Like.objects.filter(post__author=user).count()

        # Commenti fatti dall'utente
        comments_count = Comment.objects.filter(author=user).count()

        return Response({
            'postCount': post_count,
            'likesCount': likes_count,
            'commentsCount': comments_count
        })

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Restituisce la classifica degli utenti più attivi."""
        # Ottieni il parametro opzionale per il gruppo
        group_id = request.query_params.get('group_id', None)

        # Base query per ottenere utenti con conteggio like
        queryset = Utente.objects.annotate(
            post_count=Count('posts', distinct=True),
            like_count=Count('posts__likes', distinct=True),
            comment_count=Count('comments', distinct=True),
            total_score=Count('posts', distinct=True) +
                        (Count('posts__likes', distinct=True) * 2) +
                        Count('comments', distinct=True)
        )

        # Se specificato, filtra per gruppo
        if group_id:
            try:
                group = Gruppo.objects.get(id=group_id)
                queryset = queryset.filter(
                    memberships__group=group
                )
            except Gruppo.DoesNotExist:
                return Response(
                    {"detail": "Gruppo non trovato."},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Ordina per punteggio totale
        queryset = queryset.order_by('-total_score')[:10]

        # Serializza i risultati
        data = []
        for user in queryset:
            # Ottieni i badge dell'utente
            user_badges = UserBadge.objects.filter(user=user)
            badges = [
                {
                    "id": ub.badge.id,
                    "name": ub.badge.name,
                    "description": ub.badge.description,
                    "icon_url": request.build_absolute_uri(ub.badge.icon_url.url) if ub.badge.icon_url else None
                } for ub in user_badges
            ]

            data.append({
                "id": user.id,
                "username": user.username,
                "profile_picture": request.build_absolute_uri(
                    user.profile_picture.url) if user.profile_picture else None,
                "post_count": user.post_count,
                "like_count": user.like_count,
                "comment_count": user.comment_count,
                "total_score": user.total_score,
                "badges": badges
            })

        return Response(data)

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

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """
        Get all chat messages for a group
        """
        group = self.get_object()
        # Verifica che l'utente faccia parte del gruppo
        if not group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ottieni i messaggi di chat ordinati per data
        messages = DiaryPost.objects.filter(
            group=group,
            is_chat_message=True
        ).order_by('created_at')

        serializer = DiaryPostSerializer(
            messages,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """
        Send a chat message to a group
        """
        group = self.get_object()
        # Verifica che l'utente faccia parte del gruppo
        if not group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        content = request.data.get('content', '')
        if not content:
            return Response(
                {"detail": "Message content is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea il messaggio
        message = DiaryPost.objects.create(
            group=group,
            author=request.user,
            title="Chat message",
            content=content,
            is_chat_message=True
        )

        serializer = DiaryPostSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        post = serializer.save(author=self.request.user)
        # Verifica i badge dopo la creazione di un post
        BadgeService.check_all_badges(self.request.user)
        return post

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        post = self.get_object()

        # Check if already liked
        if Like.objects.filter(user=request.user, post=post).exists():
            return Response({"detail": "You've already liked this post."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create like
        like = Like.objects.create(user=request.user, post=post)

        # Verifica i badge per l'autore del post dopo aver ricevuto un like
        BadgeService.check_all_badges(post.author)

        serializer = LikeSerializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PostMediaViewSet(viewsets.ModelViewSet):
    queryset = PostMedia.objects.all()
    serializer_class = PostMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def perform_create(self, serializer):
        media = serializer.save()
        # Verifica i badge dopo il caricamento di un media
        BadgeService.check_all_badges(media.post.author)
        return media

    @action(detail=False, methods=['post'])
    def upload_media(self, request):
        """
        Upload a media file (image or video) for a diary post
        """
        post_id = request.data.get('post_id')
        if not post_id:
            return Response(
                {"detail": "Post ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            post = DiaryPost.objects.get(id=post_id)
        except DiaryPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica che l'utente sia l'autore del post o un membro del gruppo
        if post.author != request.user and not post.group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che ci sia un file media
        if 'media_file' not in request.FILES:
            return Response(
                {"detail": "No media file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determina il tipo di media (immagine o video)
        file = request.FILES['media_file']
        file_name = file.name.lower()
        if file_name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            media_type = 'image'
        elif file_name.endswith(('.mp4', '.mov', '.avi')):
            media_type = 'video'
        else:
            return Response(
                {"detail": "Unsupported file type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea il media
        media = PostMedia.objects.create(
            post=post,
            media_type=media_type,
            media_url=file,
            latitude=request.data.get('latitude'),
            longitude=request.data.get('longitude'),
            detected_objects=request.data.get('detected_objects'),
            ocr_text=request.data.get('ocr_text'),
            caption=request.data.get('caption')
        )

        # Verifica i badge dopo il caricamento di un media
        BadgeService.check_all_badges(request.user)

        serializer = PostMediaSerializer(media)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def upload_chat_image(self, request):
        """
        Upload an image for a chat message
        """
        group_id = request.data.get('group_id')
        if not group_id:
            return Response(
                {"detail": "Group ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            group = Gruppo.objects.get(id=group_id)
        except Gruppo.DoesNotExist:
            return Response(
                {"detail": "Group not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica che l'utente faccia parte del gruppo
        if not group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che ci sia un'immagine
        if 'media_file' not in request.FILES:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea un post per il messaggio di chat
        post = DiaryPost.objects.create(
            group=group,
            author=request.user,
            title="Chat image",
            content="",
            is_chat_message=True
        )

        # Crea il media
        media = PostMedia.objects.create(
            post=post,
            media_type='image',
            media_url=request.FILES['media_file']
        )

        # Verifica i badge dopo il caricamento di un'immagine in chat
        BadgeService.check_all_badges(request.user)

        # Restituisci l'URL dell'immagine
        serializer = PostMediaSerializer(media)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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