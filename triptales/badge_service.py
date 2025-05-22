# Nuovo file: triptales/badge_service.py
from .models import Badge, UserBadge, Utente, DiaryPost, PostMedia
from django.db.models import Count, Q, Sum


class BadgeService:
    """Servizio per gestire l'assegnazione di badge agli utenti."""

    @staticmethod
    def check_all_badges(user):
        """Verifica tutti i possibili badge per un utente."""
        BadgeService.check_explorer_badge(user)
        BadgeService.check_translator_badge(user)
        BadgeService.check_observer_badge(user)
        BadgeService.check_photographer_badge(user)
        BadgeService.check_social_badge(user)

    @staticmethod
    def check_explorer_badge(user):
        """Verifica se l'utente merita il badge 'Esploratore'."""
        # Assegna questo badge se l'utente ha creato post in 5+ luoghi diversi
        distinct_locations = DiaryPost.objects.filter(
            author=user,
            location_name__isnull=False
        ).values('location_name').distinct().count()

        if distinct_locations >= 5:
            explorer_badge = Badge.objects.get_or_create(
                name="Esploratore",
                defaults={
                    'description': 'Hai visitato 5 o più luoghi diversi!',
                    'icon_url': 'badge_icons/explorer.png',
                    'criteria': {'locations': 5}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=explorer_badge)

    @staticmethod
    def check_translator_badge(user):
        """Verifica se l'utente merita il badge 'Traduttore'."""
        # Assegna questo badge se l'utente ha utilizzato OCR + traduzione in 3+ post
        ocr_count = PostMedia.objects.filter(
            post__author=user,
            ocr_text__isnull=False,
            ocr_text__gt=''
        ).count()

        if ocr_count >= 3:
            translator_badge = Badge.objects.get_or_create(
                name="Traduttore",
                defaults={
                    'description': 'Hai tradotto testo in 3 o più post!',
                    'icon_url': 'badge_icons/translator.png',
                    'criteria': {'translations': 3}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=translator_badge)

    @staticmethod
    def check_observer_badge(user):
        """Verifica se l'utente merita il badge 'Osservatore'."""
        # Assegna questo badge se l'utente ha riconosciuto oggetti in 10+ post
        object_detection_count = PostMedia.objects.filter(
            post__author=user,
            detected_objects__isnull=False
        ).count()

        if object_detection_count >= 10:
            observer_badge = Badge.objects.get_or_create(
                name="Osservatore",
                defaults={
                    'description': 'Hai riconosciuto oggetti in 10 o più post!',
                    'icon_url': 'badge_icons/observer.png',
                    'criteria': {'object_detections': 10}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=observer_badge)

    @staticmethod
    def check_photographer_badge(user):
        """Verifica se l'utente merita il badge 'Fotografo'."""
        # Assegna questo badge se l'utente ha caricato 20+ foto
        photo_count = PostMedia.objects.filter(
            post__author=user,
            media_type='image'
        ).count()

        if photo_count >= 20:
            photographer_badge = Badge.objects.get_or_create(
                name="Fotografo",
                defaults={
                    'description': 'Hai caricato 20 o più foto!',
                    'icon_url': 'badge_icons/photographer.png',
                    'criteria': {'photos': 20}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=photographer_badge)

    @staticmethod
    def check_social_badge(user):
        """Verifica se l'utente merita il badge 'Social'."""
        # Assegna questo badge se l'utente ha ricevuto 15+ like
        like_count = user.posts.annotate(like_count=Count('likes')).aggregate(
            total_likes=Sum('like_count')
        )['total_likes'] or 0

        if like_count >= 15:
            social_badge = Badge.objects.get_or_create(
                name="Social",
                defaults={
                    'description': 'I tuoi post hanno ricevuto 15 o più like!',
                    'icon_url': 'badge_icons/social.png',
                    'criteria': {'likes': 15}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=social_badge)

    @staticmethod
    def check_ai_explorer_badge(user):
        """Verifica se l'utente merita il badge 'AI Explorer'."""
        # Badge per chi usa tutte le funzionalità ML Kit
        ml_features_used = 0

        # Controlla OCR usage
        if PostMedia.objects.filter(
                post__author=user,
                ocr_text__isnull=False,
                ocr_text__gt=''
        ).exists():
            ml_features_used += 1

        # Controlla Object Detection usage
        if PostMedia.objects.filter(
                post__author=user,
                detected_objects__isnull=False
        ).exists():
            ml_features_used += 1

        # Controlla Caption generation usage
        if PostMedia.objects.filter(
                post__author=user,
                caption__isnull=False,
                caption__gt=''
        ).exists():
            ml_features_used += 1

        if ml_features_used >= 3:  # Ha usato tutte e 3 le funzionalità
            ai_explorer_badge = Badge.objects.get_or_create(
                name="AI Explorer",
                defaults={
                    'description': 'Hai sfruttato tutte le funzionalità AI: OCR, riconoscimento oggetti e caption intelligenti!',
                    'icon_url': 'badge_icons/ai_explorer.png',
                    'criteria': {'ml_features': 3}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=ai_explorer_badge)

    @staticmethod
    def check_polyglot_badge(user):
        """Verifica se l'utente merita il badge 'Polyglot'."""
        # Badge per chi usa spesso la traduzione
        translation_count = PostMedia.objects.filter(
            post__author=user,
            ocr_text__isnull=False,
            ocr_text__gt=''
        ).count()

        if translation_count >= 10:
            polyglot_badge = Badge.objects.get_or_create(
                name="Polyglot",
                defaults={
                    'description': 'Maestro delle lingue! Hai tradotto testo in 10+ foto diverse.',
                    'icon_url': 'badge_icons/polyglot.png',
                    'criteria': {'translations': 10}
                }
            )[0]

            UserBadge.objects.get_or_create(user=user, badge=polyglot_badge)

    # Aggiorna il metodo check_all_badges
    @staticmethod
    def check_all_badges(user):
        """Verifica tutti i possibili badge per un utente."""
        BadgeService.check_explorer_badge(user)
        BadgeService.check_translator_badge(user)
        BadgeService.check_observer_badge(user)
        BadgeService.check_photographer_badge(user)
        BadgeService.check_social_badge(user)
        # NUOVI badge ML Kit
        BadgeService.check_ai_explorer_badge(user)
        BadgeService.check_polyglot_badge(user)