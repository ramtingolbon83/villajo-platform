from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminAccountViewSet,
    AvailabilitySlotViewSet,
    MeView,
    RegisterCustomerView,
    ReservationViewSet,
    TaskViewSet,
    WorkTimeViewSet,
)

app_name = "accounts"

router = DefaultRouter()
router.register(r"admin/accounts", AdminAccountViewSet, basename="admin-account")
router.register(r"availability", AvailabilitySlotViewSet, basename="availability")
router.register(r"reservations", ReservationViewSet, basename="reservation")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"worktime", WorkTimeViewSet, basename="worktime")

urlpatterns = [
    path("auth/register/", RegisterCustomerView.as_view(), name="register"),
    path("accounts/me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]