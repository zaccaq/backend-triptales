from rest_framework import permissions
from .models import GroupMembership


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the author/owner
        if hasattr(obj, 'author'):
            return obj.author == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsMemberOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow members of a group to create/edit content in it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is a member of the group
        if hasattr(obj, 'group'):
            return GroupMembership.objects.filter(user=request.user, group=obj.group).exists()
        return False


class IsGroupAdmin(permissions.BasePermission):
    """
    Custom permission to only allow group admins to perform certain actions.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is an admin of the group
        if hasattr(obj, 'group'):
            group = obj.group
        elif hasattr(obj, 'membership'):
            group = obj.membership.group
        else:
            return False

        return GroupMembership.objects.filter(
            user=request.user,
            group=group,
            role='admin'
        ).exists()