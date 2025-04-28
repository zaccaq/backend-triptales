from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TripGroupViewSet, PostViewSet, CommentViewSet, BadgeViewSet
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'groups', TripGroupViewSet)
router.register(r'posts', PostViewSet)
router.register(r'comments', CommentViewSet)
router.register(r'badges', BadgeViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
