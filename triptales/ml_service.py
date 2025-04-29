import json
import os
from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


# Note: This is a placeholder service for ML Kit integration
# In a real implementation, you would use Firebase ML Kit with Android

class MLService:
    """
    Mock service for ML Kit functionality that would be implemented client-side
    For demonstration of how backend would handle ML Kit results from Android
    """

    @staticmethod
    def detect_objects(image_path):
        """
        Mock implementation of object detection
        In a real app, this would be done client-side with ML Kit
        """
        # Simulating object detection results
        objects = [
            {"label": "monument", "confidence": 0.92},
            {"label": "landmark", "confidence": 0.87},
            {"label": "building", "confidence": 0.76},
        ]
        return objects

    @staticmethod
    def extract_text(image_path):
        """
        Mock implementation of OCR text extraction
        In a real app, this would be done client-side with ML Kit
        """
        # Simulating OCR results
        text = "Example text extracted from the image. This could be text from a monument plaque or information sign."
        return text

    @staticmethod
    def translate_text(text, target_language='en'):
        """
        Mock implementation of text translation
        In a real app, this would be done client-side with ML Kit
        """
        # Simulating translation results
        if text:
            return f"Translated text to {target_language}: {text}"
        return ""

    @staticmethod
    def generate_caption(image_path, detected_objects=None):
        """
        Mock implementation of image captioning based on detected objects
        In a real app, this might integrate client ML Kit data with a backend service
        """
        if detected_objects:
            primary_object = detected_objects[0]['label'] if detected_objects else "scene"
            return f"A beautiful {primary_object} captured during our trip."
        return "A beautiful scene captured during our trip."


# API endpoint to receive ML Kit results from Android client
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_ml_results(request):
    """
    Endpoint to receive ML Kit processing results from Android client
    """
    data = request.data
    post_id = data.get('post_id')
    ml_results = data.get('ml_results', {})

    if not post_id:
        return Response({"error": "post_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import PostMedia, DiaryPost, Badge, UserBadge

        post = DiaryPost.objects.get(id=post_id)

        # Ensure user has permission (is post author or group member)
        if post.author != request.user and not post.group.memberships.filter(user=request.user).exists():
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        # Find associated media or create new one
        media_id = data.get('media_id')
        if media_id:
            media = PostMedia.objects.get(id=media_id)
        else:
            # Create new media entry if media_id not provided
            media_file = request.FILES.get('media_file')
            if not media_file:
                return Response({"error": "media_file is required for new media"},
                                status=status.HTTP_400_BAD_REQUEST)

            media = PostMedia.objects.create(
                post=post,
                media_type=data.get('media_type', 'image'),
                media_url=media_file
            )

        # Update media with ML Kit results
        if 'detected_objects' in ml_results:
            media.detected_objects = ml_results['detected_objects']

        if 'ocr_text' in ml_results:
            media.ocr_text = ml_results['ocr_text']

        if 'caption' in ml_results:
            media.caption = ml_results['caption']

        # If location data is provided, update it
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude and longitude:
            media.latitude = float(latitude)
            media.longitude = float(longitude)

        media.save()

        # Check for badge eligibility
        check_badge_eligibility(request.user)

        return Response({
            "id": media.id,
            "message": "ML Kit results processed successfully",
            "results": ml_results
        }, status=status.HTTP_200_OK)

    except DiaryPost.DoesNotExist:
        return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
    except PostMedia.DoesNotExist:
        return Response({"error": "Media not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def check_badge_eligibility(user):
    """Check if user qualifies for any badges based on their activity"""
    from .models import Badge, UserBadge, PostMedia, DiaryPost

    # Example: Check for "Translator" badge (used OCR and translation)
    translator_badge = Badge.objects.filter(name="Traduttore").first()
    if translator_badge:
        # Check if user has posts with OCR text
        ocr_count = PostMedia.objects.filter(
            post__author=user,
            ocr_text__isnull=False,
            ocr_text__gt=''
        ).count()

        if ocr_count >= 5 and not UserBadge.objects.filter(user=user, badge=translator_badge).exists():
            UserBadge.objects.create(user=user, badge=translator_badge)

    # Example: Check for "Observer" badge (detected multiple objects)
    observer_badge = Badge.objects.filter(name="Osservatore").first()
    if observer_badge:
        # Check if user has posts with detected objects
        object_detection_count = PostMedia.objects.filter(
            post__author=user,
            detected_objects__isnull=False
        ).count()

        if object_detection_count >= 10 and not UserBadge.objects.filter(user=user, badge=observer_badge).exists():
            UserBadge.objects.create(user=user, badge=observer_badge)