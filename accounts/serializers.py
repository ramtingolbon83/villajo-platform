from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import Account, AvailabilitySlot, Reservation, Task, WorkTime


# ==================================================
#                      Mixins
# ==================================================
class NormalizedEmailMixin:
    """Normalize the email and reject duplicates regardless of letter case."""

    def validate_email(self, value):
        value = value.strip().lower()
        qs = Account.objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return value


# ==================================================
#                  Customer Registration
# ==================================================
class CustomerRegistrationSerializer(NormalizedEmailMixin, serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, validators=[validate_password], trim_whitespace=False
    )

    class Meta:
        model = Account
        fields = (
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        # Role and flags are never taken from the request
        validated_data.update(
            role=Account.Role.CUSTOMER, is_active=True, is_verified=False
        )
        return Account.objects.create_user(**validated_data)


# ==================================================
#                   Current User (Me)
# ==================================================
class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "is_active",
            "is_verified",
            "date_joined",
            "last_login",
        )
        # Only name and phone are editable by the user themselves
        read_only_fields = (
            "id",
            "email",
            "role",
            "is_active",
            "is_verified",
            "date_joined",
            "last_login",
        )


# ==================================================
#                  Admin Management
# ==================================================
class AdminAccountSerializer(NormalizedEmailMixin, serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        trim_whitespace=False,
    )

    class Meta:
        model = Account
        fields = (
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "is_active",
            "is_verified",
            "is_staff",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login", "is_staff")

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError(
                {"password": "Required on account creation."}
            )
        return Account.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ==================================================
#                    Reservations
# ==================================================
class ReservationSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_count = serializers.IntegerField(min_value=1, default=1)

    class Meta:
        model = Reservation
        fields = (
            "id",
            "customer",
            "property_obj",
            "starts_at",
            "ends_at",
            "guest_count",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "customer", "status", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        # Only Admin/Owner may change status; for customers it is server-controlled
        if user and getattr(user, "role", None) in (
            Account.Role.ADMIN,
            Account.Role.OWNER,
        ):
            self.fields["status"].read_only = False

    def validate(self, attrs):
        # Status-only changes (confirm, cancel, complete) skip the booking checks
        changes_booking = self.instance is None or any(
            key in attrs
            for key in ("starts_at", "ends_at", "property_obj", "guest_count")
        )
        if not changes_booking:
            return attrs

        start = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        end = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        prop = attrs.get("property_obj", getattr(self.instance, "property_obj", None))
        guests = attrs.get("guest_count", getattr(self.instance, "guest_count", 1))

        if start and end and end <= start:
            raise serializers.ValidationError(
                {"ends_at": "Must be later than starts_at."}
            )
        if start and "starts_at" in attrs and start <= timezone.now():
            raise serializers.ValidationError({"starts_at": "Must be in the future."})
        if prop and not (prop.status == "published" and prop.is_active):
            raise serializers.ValidationError(
                {"property_obj": "Property is not bookable."}
            )
        if prop and guests > prop.max_guests:
            raise serializers.ValidationError({"guest_count": "Exceeds capacity."})

        if prop and start and end:
            available = AvailabilitySlot.objects.filter(
                property_obj=prop,
                status=AvailabilitySlot.Status.AVAILABLE,
                starts_at__lte=start,
                ends_at__gte=end,
            ).exists()
            if not available:
                raise serializers.ValidationError(
                    {"starts_at": "Period is not available."}
                )

            conflicts = Reservation.objects.filter(
                property_obj=prop,
                status__in=(Reservation.Status.PENDING, Reservation.Status.CONFIRMED),
                starts_at__lt=end,
                ends_at__gt=start,
            )
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError("This period is already reserved.")
        return attrs


# ==================================================
#                      Tasks
# ==================================================
class TaskSerializer(serializers.ModelSerializer):
    # Empty while the task is open; only active employees can be assigned
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(role=Account.Role.EMPLOYEE, is_active=True),
        required=False,
        allow_null=True,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "description",
            "property_obj",
            "assigned_to",
            "created_by",
            "status",
            "result",
            "due_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "status",
            "result",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        # An accepted/in-progress/completed task must keep its assignee
        # (the database enforces this too; this gives a clean 400 instead of a 500)
        if (
            self.instance is not None
            and "assigned_to" in attrs
            and attrs["assigned_to"] is None
            and self.instance.status not in (Task.Status.OPEN, Task.Status.CANCELLED)
        ):
            raise serializers.ValidationError(
                {"assigned_to": "Cannot remove the assignee of an active task."}
            )
        return attrs


# ==================================================
#                    Work Time
# ==================================================
class WorkTimeSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = WorkTime
        fields = (
            "id",
            "employee",
            "task",
            "started_at",
            "ended_at",
            "note",
            "approved",
            "created_at",
            "updated_at",
        )
        # Approval is done by a manager through a separate action, never by input
        read_only_fields = ("id", "employee", "approved", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        start = attrs.get("started_at", getattr(self.instance, "started_at", None))
        end = attrs.get("ended_at", getattr(self.instance, "ended_at", None))
        task = attrs.get("task", getattr(self.instance, "task", None))
        is_employee = getattr(user, "role", None) == Account.Role.EMPLOYEE

        if start and end and end <= start:
            raise serializers.ValidationError(
                {"ended_at": "Must be later than started_at."}
            )

        # An approved record is final for the employee who logged it
        if self.instance is not None and self.instance.approved and is_employee:
            raise serializers.ValidationError(
                "An approved work time can no longer be edited."
            )

        if task and is_employee and task.assigned_to_id != user.id:
            raise serializers.ValidationError({"task": "Task must be assigned to you."})

        # An employee cannot log two overlapping periods
        employee = self.instance.employee if self.instance else user
        if employee is not None and start and end:
            overlaps = WorkTime.objects.filter(
                employee=employee, started_at__lt=end, ended_at__gt=start
            )
            if self.instance:
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError(
                    "This period overlaps with another work time."
                )
        return attrs


# ==================================================
#                   Availability
# ==================================================
class AvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = (
            "id",
            "property_obj",
            "starts_at",
            "ends_at",
            "status",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        start = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        end = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        prop = attrs.get("property_obj", getattr(self.instance, "property_obj", None))

        if start and end and end <= start:
            raise serializers.ValidationError(
                {"ends_at": "Must be later than starts_at."}
            )

        # Slots of one property must not overlap each other
        if prop and start and end:
            overlaps = AvailabilitySlot.objects.filter(
                property_obj=prop, starts_at__lt=end, ends_at__gt=start
            )
            if self.instance:
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError(
                    "This period overlaps with another availability slot."
                )
        return attrs
