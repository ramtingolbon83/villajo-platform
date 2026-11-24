from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "ADMIN")
    )


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_admin(request.user)


class IsPropertyOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or is_admin(request.user):
            return True
        # Works for Property itself and for objects that point to it
        prop = getattr(obj, "property_obj", obj)
        return prop.owner_id == request.user.id