from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# ==================================================
#                      Base
# ==================================================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="تاریخ آخرین بروزرسانی"
    )

    class Meta:
        abstract = True


# ==================================================
#                     Accounts
# ==================================================
class AccountManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("role", Account.Role.CUSTOMER)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Account.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have staff and superuser flags")
        return self.create_user(email, password, **extra_fields)


class Account(AbstractUser, TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        OWNER = "OWNER", "Owner"
        EMPLOYEE = "EMPLOYEE", "Employee"
        CUSTOMER = "CUSTOMER", "Customer"

    # Login (email instead of username)
    username = None
    email = models.EmailField(unique=True)

    # Profile
    phone_number = models.CharField(max_length=32, blank=True)

    # Access
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ()
    objects = AccountManager()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


# ==================================================
#                     Audit Log
# ==================================================
class AuditEvent(models.Model):
    # Who
    actor = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )

    # What
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)

    # Where from
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    # When
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


# ==================================================
#                   Availability
# ==================================================
class AvailabilitySlot(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "در دسترس"
        BLOCKED = "BLOCKED", "مسدود"

    # Relation
    property_obj = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="availability_slots",
        verbose_name="اقامتگاه",
    )

    # Period
    starts_at = models.DateTimeField(verbose_name="شروع")
    ends_at = models.DateTimeField(verbose_name="پایان")

    # Status
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="وضعیت",
    )
    note = models.CharField(max_length=250, blank=True, verbose_name="یادداشت")

    class Meta:
        verbose_name = "بازه‌ی دسترسی"
        verbose_name_plural = "بازه‌های دسترسی"
        ordering = ("starts_at",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="availability_end_after_start",
            ),
        )
        indexes = (models.Index(fields=["property_obj", "starts_at", "ends_at"]),)

    def __str__(self):
        return f"{self.property_obj} - {self.starts_at:%Y-%m-%d}"


# ==================================================
#                   Reservations
# ==================================================
class Reservation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "در انتظار"
        CONFIRMED = "CONFIRMED", "تأیید شده"
        CANCELLED = "CANCELLED", "لغو شده"
        COMPLETED = "COMPLETED", "تکمیل شده"

    # Relations
    customer = models.ForeignKey(
        "Account",
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="مشتری",
    )
    property_obj = models.ForeignKey(
        "properties.Property",
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="اقامتگاه",
    )

    # Stay
    starts_at = models.DateTimeField(verbose_name="ورود")
    ends_at = models.DateTimeField(verbose_name="خروج")
    guest_count = models.PositiveSmallIntegerField(
        default=1, verbose_name="تعداد مهمان"
    )

    # Status
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت",
    )

    class Meta:
        verbose_name = "رزرو"
        verbose_name_plural = "رزروها"
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="reservation_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(guest_count__gte=1),
                name="reservation_guest_count_positive",
            ),
        )
        indexes = (
            models.Index(fields=["property_obj", "starts_at", "ends_at"]),
            models.Index(fields=["customer", "status"]),
        )

    def __str__(self):
        return f"{self.customer} - {self.property_obj} - {self.starts_at:%Y-%m-%d}"


# ==================================================
#                      Tasks
# ==================================================
class Task(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "باز"
        ACCEPTED = "ACCEPTED", "پذیرفته شده"
        IN_PROGRESS = "IN_PROGRESS", "در حال انجام"
        COMPLETED = "COMPLETED", "تکمیل شده"
        CANCELLED = "CANCELLED", "لغو شده"

    # Content
    title = models.CharField(max_length=200, verbose_name="عنوان")
    description = models.TextField(blank=True, verbose_name="توضیحات")

    # Relations
    property_obj = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name="اقامتگاه",
    )
    # Empty while the task is open; required once it is accepted (see constraint)
    assigned_to = models.ForeignKey(
        "Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        verbose_name="مسئول انجام",
    )
    created_by = models.ForeignKey(
        "Account",
        on_delete=models.PROTECT,
        related_name="created_tasks",
        verbose_name="ایجادکننده",
    )

    # Status & Result
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        verbose_name="وضعیت",
    )
    result = models.TextField(blank=True, verbose_name="نتیجه")
    due_at = models.DateTimeField(null=True, blank=True, verbose_name="مهلت")

    class Meta:
        verbose_name = "تسک"
        verbose_name_plural = "تسک‌ها"
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(assigned_to__isnull=False)
                    | models.Q(status__in=["OPEN", "CANCELLED"])
                ),
                name="task_active_status_requires_assignee",
            ),
        )
        indexes = (models.Index(fields=["assigned_to", "status"]),)

    def __str__(self):
        return self.title


# ==================================================
#                    Work Time
# ==================================================
class WorkTime(TimeStampedModel):
    # Relations
    employee = models.ForeignKey(
        "Account",
        on_delete=models.PROTECT,
        related_name="work_times",
        verbose_name="کارمند",
    )
    task = models.ForeignKey(
        "Task",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_times",
        verbose_name="تسک",
    )

    # Period
    started_at = models.DateTimeField(verbose_name="شروع")
    ended_at = models.DateTimeField(verbose_name="پایان")

    # Details
    note = models.CharField(max_length=500, blank=True, verbose_name="یادداشت")
    approved = models.BooleanField(default=False, verbose_name="تأیید شده")

    class Meta:
        verbose_name = "زمان کاری"
        verbose_name_plural = "زمان‌های کاری"
        ordering = ("-started_at",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(ended_at__gt=models.F("started_at")),
                name="worktime_end_after_start",
            ),
        )
        indexes = (models.Index(fields=["employee", "started_at"]),)

    def __str__(self):
        return f"{self.employee} - {self.started_at:%Y-%m-%d}"