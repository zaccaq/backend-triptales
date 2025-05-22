from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import ml_service

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'trip-groups', views.TripGroupViewSet)
router.register(r'group-memberships', views.GroupMembershipViewSet)
router.register(r'diary-posts', views.DiaryPostViewSet)
router.register(r'post-media', views.PostMediaViewSet)
router.register(r'comments', views.CommentViewSet)
router.register(r'badges', views.BadgeViewSet)
router.register(r'user-badges', views.UserBadgeViewSet)
router.register(r'group-invites', views.GroupInviteViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('ml-results/', ml_service.process_ml_results, name='process-ml-results'),
    path('users/me/stats/', views.UserViewSet.as_view({'get': 'stats'}), name='user-stats'),
    path('users/leaderboard/', views.UserViewSet.as_view({'get': 'leaderboard'}), name='user-leaderboard'),
    path('api/trip-groups/my/', views.TripGroupViewSet.as_view({'get': 'my'}), name='my-groups'),
    path('trip-groups/my_invites/', views.GroupInviteViewSet.as_view({'get': 'my_invites'}), name='my-invites'),
    path('api/trip-groups/search/', views.TripGroupViewSet.as_view({'get': 'search'}), name='group-search'),
    path('api/trip-groups/<int:pk>/map_posts/', views.TripGroupViewSet.as_view({'get': 'map_posts'}), name='group-map-posts'),
    path('api/trip-groups/<int:pk>/add_location_post/', views.TripGroupViewSet.as_view({'post': 'add_location_post'}), name='add-location-post'),
]
