from django.db import models
from rest_framework import viewsets, permissions, status, filters, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Utente, Gruppo, GroupMembership, DiaryPost, PostMedia, Comment, Like, Badge, UserBadge
from .serializers import (UserSerializer, TripGroupSerializer, GroupMembershipSerializer,
                          DiaryPostSerializer, PostMediaSerializer, CommentSerializer,
                          LikeSerializer, BadgeSerializer, UserBadgeSerializer, GroupInvite, GroupInviteSerializer)
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


# In triptales/views.py

class TripGroupViewSet(viewsets.ModelViewSet):
    queryset = Gruppo.objects.all()
    serializer_class = TripGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'location']

    # Aggiungi questo metodo alla classe TripGroupViewSet in triptales/views.py

    @action(detail=True, methods=['get'])
    def map_posts(self, request, pk=None):
        """
        Restituisce tutti i post con geolocalizzazione per la mappa del gruppo
        """
        group = self.get_object()

        # Verifica che l'utente faccia parte del gruppo
        if not group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ottieni i post con coordinate valide
        posts_with_location = DiaryPost.objects.filter(
            group=group,
            is_chat_message=False,  # Esclude i messaggi chat
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('author').prefetch_related('media', 'likes').order_by('-created_at')

        # Serializza i dati per la mappa
        map_data = []
        for post in posts_with_location:
            # Prendi la prima immagine se disponibile
            first_image = post.media.filter(media_type='image').first()

            map_data.append({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'latitude': post.latitude,
                'longitude': post.longitude,
                'location_name': post.location_name or 'Posizione sconosciuta',
                'created_at': post.created_at,
                'author': {
                    'id': post.author.id,
                    'username': post.author.username,
                    'profile_picture': request.build_absolute_uri(
                        post.author.profile_picture.url) if post.author.profile_picture else None
                },
                'image_url': request.build_absolute_uri(first_image.media_url.url) if first_image else None,
                'likes_count': post.likes.count(),
                'user_has_liked': post.likes.filter(user=request.user).exists()
            })

        return Response({
            'group_name': group.name,
            'group_location': group.location,
            'posts': map_data
        })

    @action(detail=True, methods=['post'])
    def add_location_post(self, request, pk=None):
        """
        Crea un nuovo post con geolocalizzazione
        """
        group = self.get_object()

        # Verifica che l'utente faccia parte del gruppo
        if not group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Dati richiesti
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        location_name = request.data.get('location_name', '')

        if not title or not content:
            return Response(
                {"detail": "Title and content are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not latitude or not longitude:
            return Response(
                {"detail": "Latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Crea il post
            post = DiaryPost.objects.create(
                group=group,
                author=request.user,
                title=title,
                content=content,
                latitude=float(latitude),
                longitude=float(longitude),
                location_name=location_name
            )

            # Se c'è un'immagine, aggiungila
            if 'image' in request.FILES:
                PostMedia.objects.create(
                    post=post,
                    media_type='image',
                    media_url=request.FILES['image'],
                    latitude=float(latitude),
                    longitude=float(longitude)
                )

            # Verifica i badge dopo la creazione di un post con posizione
            BadgeService.check_all_badges(request.user)

            serializer = DiaryPostSerializer(post, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response(
                {"detail": "Invalid latitude or longitude values."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Error creating post: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def my(self, request):
        """Restituisce i gruppi dell'utente corrente."""
        user = request.user
        # Ottieni tutti i gruppi di cui l'utente è membro
        memberships = GroupMembership.objects.filter(user=user)
        groups = []

        for membership in memberships:
            group = membership.group
            # Trova l'ultimo post o messaggio nel gruppo
            last_activity = DiaryPost.objects.filter(group=group).order_by('-created_at').first()

            # Aggiungi campo lastActivityDate al gruppo
            setattr(group, 'lastActivityDate',
                    last_activity.created_at if last_activity else group.created_at)

            # Aggiungi campo user_role al gruppo
            setattr(group, 'user_role', membership.role)

            groups.append(group)

        serializer = self.get_serializer(groups, many=True, context={'request': request})
        return Response(serializer.data)

    def perform_create(self, serializer):
        try:
            # Crea il gruppo con l'utente corrente come creatore e il parametro is_private
            is_private = self.request.data.get('is_private', False)
            group = serializer.save(created_by=self.request.user, is_private=is_private)

            # Aggiungi automaticamente il creatore come admin del gruppo
            membership = GroupMembership.objects.create(
                user=self.request.user,
                group=group,
                role='admin'
            )

            # Log dell'operazione per debug
            print(f"Gruppo {group.id} creato da {self.request.user.username} con ruolo admin")

            return group
        except Exception as e:
            # Log dell'errore
            print(f"Errore nella creazione del gruppo: {str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = self.perform_create(serializer)

        # Aggiungi informazioni sulla membership alla risposta
        response_data = serializer.data
        response_data['user_role'] = 'admin'

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        group = self.get_object()

        # Check if user is already a member
        if GroupMembership.objects.filter(user=request.user, group=group).exists():
            return Response({"detail": "You are already a member of this group."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Verifica se il gruppo è privato
        if group.is_private:
            # Verifica se esiste un invito per l'utente
            has_invite = GroupInvite.objects.filter(
                invited_user=request.user,
                group=group,
                status='pending'
            ).exists()

            if not has_invite:
                return Response(
                    {"detail": "Questo gruppo è privato. Hai bisogno di un invito per unirti."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Add user to group
        membership = GroupMembership.objects.create(
            user=request.user,
            group=group,
            role='member'
        )

        # Se c'era un invito in sospeso, segnalo come accettato
        pending_invite = GroupInvite.objects.filter(
            invited_user=request.user,
            group=group,
            status='pending'
        ).first()

        if pending_invite:
            pending_invite.status = 'accepted'
            pending_invite.save()

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

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('search', '')
        if not query:
            return Response({"detail": "Parametro di ricerca mancante"}, status=status.HTTP_400_BAD_REQUEST)

        # Cerca i gruppi che corrispondono alla query
        queryset = Gruppo.objects.filter(name__icontains=query)

        # Filtra i gruppi: mostra solo quelli pubblici O quelli di cui l'utente è membro
        user_memberships = GroupMembership.objects.filter(user=request.user).values_list('group', flat=True)
        queryset = queryset.filter(
            models.Q(is_private=False) | models.Q(id__in=user_memberships)
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # Aggiungi al TripGroupViewSet in triptales/views.py

    @action(detail=True, methods=['post'])
    def invite_user(self, request, pk=None):
        """Invita un utente al gruppo."""
        group = self.get_object()

        # Verifica che l'utente che invia l'invito sia membro del gruppo
        if not GroupMembership.objects.filter(user=request.user, group=group).exists():
            return Response(
                {"detail": "Solo i membri del gruppo possono inviare inviti."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ottieni o cerca l'utente da invitare
        user_to_invite = None
        username_or_email = request.data.get('username_or_email')

        if not username_or_email:
            return Response(
                {"detail": "Username o email dell'utente da invitare sono richiesti."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cerca l'utente per username o email
        try:
            if '@' in username_or_email:
                user_to_invite = Utente.objects.get(email=username_or_email)
            else:
                user_to_invite = Utente.objects.get(username=username_or_email)
        except Utente.DoesNotExist:
            return Response(
                {"detail": "Utente non trovato."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica che l'utente non sia già nel gruppo
        if GroupMembership.objects.filter(user=user_to_invite, group=group).exists():
            return Response(
                {"detail": "L'utente è già membro del gruppo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica che non ci sia già un invito pendente per questo utente
        if GroupInvite.objects.filter(invited_user=user_to_invite, group=group, status='pending').exists():
            return Response(
                {"detail": "Esiste già un invito pendente per questo utente."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea l'invito
        invite = GroupInvite.objects.create(
            group=group,
            invited_by=request.user,
            invited_user=user_to_invite,
            status='pending'
        )

        serializer = GroupInviteSerializer(invite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def my_invites(self, request):
        """Ottiene tutti gli inviti pendenti per l'utente corrente."""
        invites = GroupInvite.objects.filter(
            invited_user=request.user,
            status='pending'
        )
        serializer = GroupInviteSerializer(invites, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def accept_invite(self, request, pk=None):
        """Accetta un invito al gruppo."""
        try:
            invite = GroupInvite.objects.get(id=pk, invited_user=request.user, status='pending')
        except GroupInvite.DoesNotExist:
            return Response(
                {"detail": "Invito non trovato o già processato."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Aggiorna lo stato dell'invito
        invite.status = 'accepted'
        invite.save()

        # Aggiungi l'utente al gruppo
        membership = GroupMembership.objects.create(
            user=request.user,
            group=invite.group,
            role='member'
        )

        return Response(GroupMembershipSerializer(membership).data)

    @action(detail=True, methods=['post'])
    def decline_invite(self, request, pk=None):
        """Rifiuta un invito al gruppo."""
        try:
            invite = GroupInvite.objects.get(id=pk, invited_user=request.user, status='pending')
        except GroupInvite.DoesNotExist:
            return Response(
                {"detail": "Invito non trovato o già processato."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Aggiorna lo stato dell'invito
        invite.status = 'declined'
        invite.save()

        return Response({"detail": "Invito rifiutato con successo."})

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


# Aggiungi questi metodi alla classe DiaryPostViewSet in triptales/views.py

from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from rest_framework.decorators import action

# Aggiungi questi metodi alla classe DiaryPostViewSet in triptales/views.py

from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from rest_framework.decorators import action


class DiaryPostViewSet(viewsets.ModelViewSet):
    queryset = DiaryPost.objects.all()
    serializer_class = DiaryPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsMemberOrReadOnly]

    def get_queryset(self):
        """Filtra i post in base all'utente e ai suoi gruppi"""
        user = self.request.user
        # Mostra solo i post dei gruppi di cui l'utente è membro
        user_groups = user.memberships.values_list('group', flat=True)
        return DiaryPost.objects.filter(group__in=user_groups).order_by('-created_at')

    def perform_create(self, serializer):
        """Crea un nuovo post con l'autore corrente"""
        post = serializer.save(author=self.request.user)
        # Verifica i badge dopo la creazione di un post
        BadgeService.check_all_badges(self.request.user)
        return post

    @action(detail=False, methods=['get'])
    def my_posts(self, request):
        """Restituisce tutti i post dell'utente corrente"""
        posts = DiaryPost.objects.filter(
            author=request.user,
            is_chat_message=False  # Escludi i messaggi di chat
        ).order_by('-created_at')

        serializer = self.get_serializer(posts, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Restituisce i post nelle vicinanze di una posizione specifica"""
        try:
            latitude = float(request.query_params.get('latitude'))
            longitude = float(request.query_params.get('longitude'))
            radius = float(request.query_params.get('radius', 10.0))  # Default 10km
        except (TypeError, ValueError):
            return Response(
                {"error": "Parametri latitude e longitude sono richiesti e devono essere numerici"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtra i post che hanno coordinate
        posts_with_location = DiaryPost.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            is_chat_message=False
        )

        # Filtra per gruppi accessibili all'utente
        user_groups = request.user.memberships.values_list('group', flat=True)
        posts_with_location = posts_with_location.filter(group__in=user_groups)

        # Calcola la distanza e filtra
        nearby_posts = []
        for post in posts_with_location:
            distance = calculate_distance(latitude, longitude, post.latitude, post.longitude)
            if distance <= radius:
                nearby_posts.append(post)

        # Ordina per distanza (più vicini prima)
        nearby_posts.sort(key=lambda p: calculate_distance(latitude, longitude, p.latitude, p.longitude))

        serializer = self.get_serializer(nearby_posts, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/Unlike di un post"""
        post = self.get_object()

        # Verifica se l'utente può vedere questo post (è membro del gruppo)
        if not post.group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "Non hai il permesso di interagire con questo post."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Controlla se l'utente ha già messo like
        existing_like = Like.objects.filter(user=request.user, post=post).first()

        if existing_like:
            # Rimuovi il like (toggle)
            existing_like.delete()
            liked = False
            message = "Like rimosso"
        else:
            # Aggiungi il like
            Like.objects.create(user=request.user, post=post)
            liked = True
            message = "Like aggiunto"

            # Verifica i badge per l'autore del post dopo aver ricevuto un like
            BadgeService.check_all_badges(post.author)

        # Conta i like totali
        total_likes = post.likes.count()

        return Response({
            "liked": liked,
            "total_likes": total_likes,
            "message": message
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def feed(self, request):
        """Feed personalizzato dell'utente con post dei suoi gruppi"""
        user_groups = request.user.memberships.values_list('group', flat=True)

        # Ottieni post recenti dai gruppi dell'utente (non messaggi chat)
        posts = DiaryPost.objects.filter(
            group__in=user_groups,
            is_chat_message=False
        ).select_related('author', 'group').prefetch_related(
            'media', 'likes', 'comments'
        ).order_by('-created_at')[:20]  # Ultimi 20 post

        serializer = self.get_serializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calcola la distanza tra due punti geografici usando la formula di Haversine
    Restituisce la distanza in chilometri
    """
    # Converti gradi in radianti
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Formula di Haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Raggio della Terra in km
    r = 6371

    return c * r


# Aggiorna anche il PostMediaViewSet per migliorare l'upload
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
        Upload migliorato per media con supporto ML Kit
        """
        post_id = request.data.get('post_id')
        if not post_id:
            return Response(
                {"detail": "Post ID è richiesto."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            post = DiaryPost.objects.get(id=post_id)
        except DiaryPost.DoesNotExist:
            return Response(
                {"detail": "Post non trovato."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica che l'utente sia l'autore del post o un membro del gruppo
        if post.author != request.user and not post.group.memberships.filter(user=request.user).exists():
            return Response(
                {"detail": "Permesso negato."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che ci sia un file media
        if 'media_file' not in request.FILES:
            return Response(
                {"detail": "File media non fornito."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determina il tipo di media
        file = request.FILES['media_file']
        file_name = file.name.lower()
        if file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            media_type = 'image'
        elif file_name.endswith(('.mp4', '.mov', '.avi', '.mkv')):
            media_type = 'video'
        else:
            return Response(
                {"detail": "Tipo di file non supportato. Usa immagini (jpg, png, gif) o video (mp4, mov, avi)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea il media con tutti i dati opzionali
        media_data = {
            'post': post,
            'media_type': media_type,
            'media_url': file,
        }

        # Aggiungi dati opzionali se presenti
        optional_fields = ['latitude', 'longitude', 'detected_objects', 'ocr_text', 'caption']
        for field in optional_fields:
            if field in request.data and request.data[field]:
                if field in ['latitude', 'longitude']:
                    try:
                        media_data[field] = float(request.data[field])
                    except ValueError:
                        pass
                else:
                    media_data[field] = request.data[field]

        media = PostMedia.objects.create(**media_data)

        # Verifica i badge dopo il caricamento
        BadgeService.check_all_badges(request.user)

        serializer = PostMediaSerializer(media, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def process_ml_results(self, request, pk=None):
        """
        Endpoint per processare risultati ML Kit dal client Android
        """
        media = self.get_object()

        # Verifica permessi
        if media.post.author != request.user:
            return Response(
                {"detail": "Solo l'autore può aggiornare i risultati ML."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Aggiorna con i risultati ML Kit
        ml_results = request.data.get('ml_results', {})

        if 'detected_objects' in ml_results:
            media.detected_objects = ml_results['detected_objects']

        if 'ocr_text' in ml_results:
            media.ocr_text = ml_results['ocr_text']

        if 'caption' in ml_results:
            media.caption = ml_results['caption']

        media.save()

        # Verifica badge dopo il processing ML
        BadgeService.check_all_badges(request.user)

        serializer = self.get_serializer(media)
        return Response(serializer.data)


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


# Aggiungi questo nel file triptales/views.py

class GroupInviteViewSet(viewsets.ModelViewSet):
    """ViewSet per gestire gli inviti ai gruppi."""
    queryset = GroupInvite.objects.all()
    serializer_class = GroupInviteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtra gli inviti in base all'utente autenticato."""
        user = self.request.user
        return GroupInvite.objects.filter(invited_user=user, status='pending')

    @action(detail=False, methods=['get'])
    def my_invites(self, request):
        """Ottiene tutti gli inviti pendenti per l'utente corrente."""
        user = request.user
        invites = GroupInvite.objects.filter(
            invited_user=user,
            status='pending'
        )
        serializer = GroupInviteSerializer(invites, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accetta un invito al gruppo."""
        invite = self.get_object()

        # Verifica che l'invito sia per l'utente corrente
        if invite.invited_user != request.user:
            return Response(
                {"detail": "Questo invito non è per te."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che l'invito sia ancora in stato pendente
        if invite.status != 'pending':
            return Response(
                {"detail": "Questo invito è già stato processato."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Aggiorna lo stato dell'invito
        invite.status = 'accepted'
        invite.save()

        # Aggiungi l'utente al gruppo
        GroupMembership.objects.create(
            user=request.user,
            group=invite.group,
            role='member'
        )

        return Response({"detail": "Invito accettato con successo."})

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Rifiuta un invito al gruppo."""
        invite = self.get_object()

        # Verifica che l'invito sia per l'utente corrente
        if invite.invited_user != request.user:
            return Response(
                {"detail": "Questo invito non è per te."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che l'invito sia ancora in stato pendente
        if invite.status != 'pending':
            return Response(
                {"detail": "Questo invito è già stato processato."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Aggiorna lo stato dell'invito
        invite.status = 'declined'
        invite.save()

        return Response({"detail": "Invito rifiutato con successo."})