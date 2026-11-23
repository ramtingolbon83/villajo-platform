from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Account, AvailabilitySlot, Reservation, Task, WorkTime
from .serializers import (
    AdminAccountSerializer,
    AvailabilitySlotSerializer,
    CustomerRegistrationSerializer,
    MeSerializer,
    ReservationSerializer,
    TaskSerializer,
    WorkTimeSerializer,
)
from .services import write_audit


# ==================================================
#                  Helpers & Permissions
# ==================================================
def is_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role == Account.Role.ADMIN)
    )


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_active and is_admin(user))


# ==================================================
#                      Accounts
# ==================================================
class RegisterCustomerView(generics.CreateAPIView):
    queryset = Account.objects.all()
    serializer_class = CustomerRegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "anon"


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        if not self.request.user.is_active:
            raise PermissionDenied("Inactive account.")
        return self.request.user


class AdminAccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by("-date_joined")
    serializer_class = AdminAccountSerializer
    permission_classes = (IsAdmin,)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        account = self.get_object()
        if account.pk == request.user.pk:
            return Response(
                {"detail": "Cannot deactivate your own account."}, status=400
            )
        account.is_active = False
        account.save(update_fields=["is_active", "updated_at"])
        return Response({"id": account.pk, "is_active": False})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        account = self.get_object()
        account.is_active = True
        account.save(update_fields=["is_active", "updated_at"])
        return Response({"id": account.pk, "is_active": True})


# ==================================================
#                   Availability
# ==================================================
class AvailabilitySlotViewSet(viewsets.ModelViewSet):
    serializer_class = AvailabilitySlotSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if not user.is_active:
            return AvailabilitySlot.objects.none()

        queryset = AvailabilitySlot.objects.select_related("property_obj")

        if is_admin(user):
            return queryset
        if user.role == Account.Role.OWNER:
            return queryset.filter(property_obj__owner=user)
        if user.role == Account.Role.CUSTOMER:
            # Customers only see open slots of published, active properties
            return queryset.filter(
                property_obj__status="published",
                property_obj__is_active=True,
                status=AvailabilitySlot.Status.AVAILABLE,
            )
        return queryset.none()

    def _allowed(self, property_obj):
        user = self.request.user
        return user.is_active and (
            is_admin(user)
            or (user.role == Account.Role.OWNER and property_obj.owner_id == user.id)
        )

    def perform_create(self, serializer):
        property_obj = serializer.validated_data["property_obj"]
        if not self._allowed(property_obj):
            raise PermissionDenied("You cannot manage availability for this property.")
        serializer.save()

    def perform_update(self, serializer):
        slot = self.get_object()
        if not self._allowed(slot.property_obj):
            raise PermissionDenied("You cannot manage availability for this property.")

        new_property = serializer.validated_data.get("property_obj", slot.property_obj)
        if new_property.pk != slot.property_obj_id:
            raise PermissionDenied("Moving slots between properties is forbidden.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._allowed(instance.property_obj):
            raise PermissionDenied("You cannot manage availability for this property.")
        instance.delete()


# ==================================================
#                   Reservations
# ==================================================
class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = Reservation.objects.select_related(
            "customer", "property_obj", "property_obj__owner"
        )
        if is_admin(user):
            return queryset
        if user.role == Account.Role.CUSTOMER:
            return queryset.filter(customer=user)
        if user.role == Account.Role.OWNER:
            return queryset.filter(property_obj__owner=user)
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != Account.Role.CUSTOMER:
            raise PermissionDenied("Only customers can book.")
        obj = serializer.save(customer=user)
        write_audit(user, "reservation.create", "Reservation", obj.pk, self.request)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = self.request.user
        changed = set(serializer.validated_data)

        if user.role == Account.Role.CUSTOMER:
            if obj.customer_id != user.id or obj.status != Reservation.Status.PENDING:
                raise PermissionDenied("Only your pending reservations can be edited.")
            if {"customer", "status", "property_obj"} & changed:
                raise PermissionDenied("Protected reservation fields.")
        elif user.role == Account.Role.OWNER:
            if obj.property_obj.owner_id != user.id:
                raise PermissionDenied("Not your property's reservation.")
            if changed - {"status"}:
                raise PermissionDenied("Owner can only update status.")
        elif not is_admin(user):
            raise PermissionDenied("Not allowed.")

        obj = serializer.save()
        write_audit(user, "reservation.update", "Reservation", obj.pk, self.request)

    def perform_destroy(self, instance):
        user = self.request.user
        if not is_admin(user):
            raise PermissionDenied("Admin only.")
        write_audit(
            user, "reservation.delete", "Reservation", instance.pk, self.request
        )
        instance.delete()


# ==================================================
#                      Tasks
# ==================================================
class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if is_admin(user):
            return Task.objects.all()
        if user.role == Account.Role.EMPLOYEE:
            # Own tasks, plus open tasks nobody has taken yet
            return Task.objects.filter(
                Q(assigned_to=user)
                | Q(assigned_to__isnull=True, status=Task.Status.OPEN)
            )
        return Task.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not is_admin(user):
            raise PermissionDenied("Admin only.")
        obj = serializer.save(created_by=user)
        write_audit(user, "task.create", "Task", obj.pk, self.request)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = self.request.user

        if user.role == Account.Role.EMPLOYEE:
            if obj.assigned_to_id != user.id:
                raise PermissionDenied("Task not assigned to you.")
            if set(serializer.validated_data) - {"status", "result"}:
                raise PermissionDenied("Employees can only update status/result.")
            new_status = serializer.validated_data.get("status")
            transitions = {
                Task.Status.OPEN: {Task.Status.ACCEPTED},
                Task.Status.ACCEPTED: {Task.Status.IN_PROGRESS, Task.Status.COMPLETED},
                Task.Status.IN_PROGRESS: {Task.Status.COMPLETED},
            }
            if new_status and new_status not in transitions.get(obj.status, set()):
                raise ValidationError({"status": "Invalid transition."})
        elif not is_admin(user):
            raise PermissionDenied("Not allowed.")

        obj = serializer.save()
        write_audit(user, "task.update", "Task", obj.pk, self.request)

    def perform_destroy(self, instance):
        user = self.request.user
        if not is_admin(user):
            raise PermissionDenied("Admin only.")
        write_audit(user, "task.delete", "Task", instance.pk, self.request)
        instance.delete()

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Take an open task, or accept one that was offered to you."""
        user = request.user
        if user.role != Account.Role.EMPLOYEE:
            raise PermissionDenied("Employees only.")

        # Row lock: two employees cannot take the same open task at once
        with transaction.atomic():
            task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
            if task.status != Task.Status.OPEN:
                raise ValidationError({"status": "Only open tasks can be accepted."})
            if task.assigned_to_id not in (None, user.id):
                raise PermissionDenied("Task is assigned to someone else.")
            task.assigned_to = user
            task.status = Task.Status.ACCEPTED
            task.save(update_fields=["assigned_to", "status", "updated_at"])

        write_audit(user, "task.accept", "Task", task.pk, request)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        obj = self.get_object()
        if (
            request.user.role != Account.Role.EMPLOYEE
            or obj.assigned_to_id != request.user.id
        ):
            raise PermissionDenied("Assigned employee only.")
        if obj.status not in (Task.Status.ACCEPTED, Task.Status.IN_PROGRESS):
            raise ValidationError({"status": "Task must be accepted first."})

        obj.status = Task.Status.COMPLETED
        obj.result = str(request.data.get("result", ""))[:10000]
        obj.save(update_fields=["status", "result", "updated_at"])
        write_audit(request.user, "task.complete", "Task", obj.pk, request)
        return Response(self.get_serializer(obj).data)


# ==================================================
#                    Work Time
# ==================================================
class WorkTimeViewSet(viewsets.ModelViewSet):
    serializer_class = WorkTimeSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        if is_admin(user):
            return WorkTime.objects.all()
        if user.role == Account.Role.EMPLOYEE:
            return WorkTime.objects.filter(employee=user)
        return WorkTime.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != Account.Role.EMPLOYEE and not is_admin(user):
            raise PermissionDenied("Employee or admin only.")
        obj = serializer.save(employee=user)
        write_audit(user, "worktime.create", "WorkTime", obj.pk, self.request)

    def perform_update(self, serializer):
        obj = self.get_object()
        user = self.request.user

        if user.role == Account.Role.EMPLOYEE:
            if obj.employee_id != user.id or obj.approved:
                raise PermissionDenied("Cannot edit this work-time record.")
            if {"employee", "approved"} & set(serializer.validated_data):
                raise PermissionDenied("Protected fields.")
        elif not is_admin(user):
            raise PermissionDenied("Not allowed.")

        obj = serializer.save()
        write_audit(user, "worktime.update", "WorkTime", obj.pk, self.request)
