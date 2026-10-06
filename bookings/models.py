# ============================================================
# Imports
# ============================================================
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.indexes import GistIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

# ============================================================
# Model Villa
# ============================================================

class Villa(models.Model):

    # -----------------------------
    # Host Information
    # -----------------------------

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="villas"
    )

    # -----------------------------
    # Basic Villa Information
    # -----------------------------

    title = models.CharField(max_length=200)

    capacity = models.PositiveIntegerField()

    # -----------------------------
    # Villa pricing Information
    # -----------------------------

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    cleaning_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    service_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    extra_guest_threshold = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    extra_guest_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # -----------------------------
    # Creation And Last Edit Time
    # -----------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -----------------------------
    # Displaying The Villa Object In Text Format
    # -----------------------------

    def __str__(self):
        return self.title


# ============================================================
# Reservation Model
# ============================================================

class Booking(models.Model):

    # -----------------------------
    # Possible Booking Situations
    # -----------------------------

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار پرداخت"
        CONFIRMED = "confirmed", "تأیید شده"
        CANCELLED = "cancelled", "لغو شده"
        EXPIRED = "expired", "منقضی شده"

    # -----------------------------
    # Stuations Where Booking Is Enabled 
    # -----------------------------

    ACTIVE_STATUSES = (
        Status.PENDING,
        Status.CONFIRMED,
    )

    # -----------------------------
    # Link Between The Reservation And The Villa
    # -----------------------------

    villa = models.ForeignKey(
        Villa,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    # -----------------------------
    # Booking Guest
    # -----------------------------

    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    # -----------------------------
    # The Person Who Made The Reservation
    # -----------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_bookings"
    )

    # -----------------------------
    # Check-In And Check -Out Dates And Times
    # -----------------------------

    check_in = models.DateTimeField()
    check_out = models.DateTimeField()

    # -----------------------------
    # Number Of Guests
    # -----------------------------

    guests_count = models.PositiveIntegerField()

    # -----------------------------
    # Current Reservation Status 
    # -----------------------------

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # -----------------------------
    # Rservation Expiration Time 
    # -----------------------------

    expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # ========================================================
    # Price Information At Ahe Time Of Booking
    # ========================================================

    nightly_price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    cleaning_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    service_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    extra_guest_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # -----------------------------
    # Save Villa Title At The Time Of Booking
    # -----------------------------

    villa_title_snapshot = models.CharField(
        max_length=200
    )

    # ========================================================
    # Reservation Cancellation Information
    # ========================================================

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_bookings"
    )

    cancellation_reason = models.TextField(
        blank=True,
        default=""
    )

    # -----------------------------
    # Creation And Last Edit Time
    # -----------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ========================================================
    # Meta Setting
    # ========================================================

    class Meta:

        # -----------------------------
        # Index For Time-Range Search
        # -----------------------------

        indexes = (
            GistIndex(
                fields=["villa", "check_in", "check_out"]
            ),
        )

        # -----------------------------
        # Limiting Simultaneous Bookings
        # -----------------------------

        constraints = (
            ExclusionConstraint(
                name="prevent_overlapping_active_bookings",
                expressions=[
                    (
                        "villa",
                        "=",
                    ),
                    (
                        models.Func(
                            models.F("check_in"),
                            models.F("check_out"),
                            function="TSTZRANGE",
                        ),
                        "&&",
                    ),
                ],
                condition=Q(
                    status__in=(
                        "pending"
                        "confirmed"
                    )
                ),
            ),
        )

    # -----------------------------
    # Display The Reservation Object As Text.
    # -----------------------------

    def __str__(self):
        return f"{self.villa.title} - {self.guest}"

    # ========================================================
    # Validation Of Booking Information
    # ========================================================

    def clean(self):

        if self.check_out <= self.check_in:
            raise ValidationError(
                "تاریخ خروج باید بعد از تاریخ ورود باشد."
            )

        if self.guests_count > self.villa.capacity:
            raise ValidationError(
                f"ظرفیت این ویلا {self.villa.capacity} نفر است."
            )

        if self.guest_id == self.villa.host_id:
            raise ValidationError(
                "میزبان نمی‌تواند برای ویلای خودش رزرو ثبت کند."
            )

    # ========================================================
    # Checking The Possibility Of Changing The Reservation Status
    # ========================================================

    def can_transition_to(self, new_status):

        allowed_transitions = {
            self.Status.PENDING: {
                self.Status.CONFIRMED,
                self.Status.CANCELLED,
                self.Status.EXPIRED,
            },

            self.Status.CONFIRMED: {
                self.Status.CANCELLED,
            },

            self.Status.CANCELLED: set(),

            self.Status.EXPIRED: set(),
        }

        return new_status in allowed_transitions.get(
            self.status,
            set()
        )


# ============================================================
# Payment Model
# ============================================================

class Payment(models.Model):

    # -----------------------------
    # Possible Payment Statuses
    # -----------------------------

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        PAID = "paid", "پرداخت موفق"
        FAILED = "failed", "ناموفق"

    # -----------------------------
    # The Reservation To Which This Payment Relates
    # -----------------------------

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    # -----------------------------
    # Payment Amount
    # -----------------------------

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # -----------------------------
    # Payment Status
    # -----------------------------

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # -----------------------------
    # Payment Transaction ID
    # -----------------------------

    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    # -----------------------------
    # Payment Gateway
    # -----------------------------

    payment_gateway = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    # -----------------------------
    # Time Of Successful Payment
    # -----------------------------

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # -----------------------------
    # Payment Creation Time
    # -----------------------------

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    # -----------------------------
    # Display Payment Object As Text
    # -----------------------------

    def __str__(self):
        return f"Payment #{self.id} - {self.amount}"
