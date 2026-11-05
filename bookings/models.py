from datetime import date
from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Func, Q, Value
from django.utils import timezone

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

# Lazy reference ("app_label.ModelName") to the villa model, which avoids a
# circular import between the bookings and properties apps.
VILLA_MODEL = "properties.Property"

# Whether infants are counted when checking a villa's guest capacity.
INFANTS_COUNT_TOWARD_CAPACITY = False

# Name of the attribute on the villa model that holds the nightly price.
VILLA_PRICE_FIELD = "price_per_night"

# Candidate attribute names on the villa model that say whether it can be
# booked. The first one found on the villa is used.
VILLA_BOOKABLE_FIELDS = ("is_bookable", "is_active")

# Name of the attribute on the villa model that holds the maximum guest count.
VILLA_CAPACITY_FIELD = "max_guests"

# Rounding step for money values (two decimal places).
CENT = Decimal("0.01")

# Name of the database-level exclusion constraint that prevents double
# bookings. API layers can match on this name to translate the resulting
# IntegrityError into a 409 Conflict response.
OVERLAP_CONSTRAINT_NAME = "booking_no_overlap_per_villa"


def local_today() -> date:
    """Return today's date in the project's time zone (respects USE_TZ)."""
    return timezone.localdate() if settings.USE_TZ else date.today()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BookingStatus(models.TextChoices):
    """
    Lifecycle states of a booking.

    Stored as short strings in the database; the second tuple element is the
    human-readable (Persian) label shown in forms, admin and serializers.
    """

    PENDING = "pending", "در انتظار پرداخت/تایید"
    CONFIRMED = "confirmed", "تایید شده"
    PAID = "paid", "پرداخت شده"
    CANCELED = "canceled", "لغو شده"
    COMPLETED = "completed", "تکمیل شده"


# Statuses that "occupy" the villa's calendar. Canceled bookings are excluded
# so their dates become available again. Used by the overlap constraint.
ACTIVE_STATUSES = [
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
    BookingStatus.PAID,
    BookingStatus.COMPLETED,
]

# Every new booking must start in this status.
INITIAL_STATUS = BookingStatus.PENDING

# State machine: maps each status to the set of statuses it may move to.
# This is the single source of truth for status changes. Terminal states
# (CANCELED, COMPLETED) have no outgoing transitions.
ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.PAID,
                            BookingStatus.CANCELED},
    BookingStatus.CONFIRMED: {BookingStatus.PAID, BookingStatus.CANCELED},
    BookingStatus.PAID: {BookingStatus.CANCELED, BookingStatus.COMPLETED},
    BookingStatus.CANCELED: set(),
    BookingStatus.COMPLETED: set(),
}

# Fields that affect the price or dates. Changing them must go through
# save() so the total is recalculated, so QuerySet.update()/bulk_update()
# (which skip save()) are blocked from touching them.
_RECALC_FIELDS = frozenset({"check_in", "check_out", "price_per_night", "final_price"})

# Fields derived automatically; they are always persisted when save() is
# called with update_fields.
_COMPUTED_FIELDS = {"final_price", "updated_at"}


class CreatedByRole(models.TextChoices):
    """The kind of user who created a booking (guest, host or admin)."""

    GUEST = "guest", "مهمان"
    HOST = "host", "میزبان"
    ADMIN = "admin", "ادمین"


def _dec(value) -> Decimal:
    """Convert a value to Decimal safely, going through str to avoid float errors."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


# ---------------------------------------------------------------------------
# QuerySet
# ---------------------------------------------------------------------------

class BookingQuerySet(models.QuerySet):

    def update(self, **kwargs):
        """Block direct bulk updates of status, price and date fields."""
        blocked = ({"status"} | _RECALC_FIELDS) & set(kwargs)
        if blocked:
            raise ValueError(
                f"تغییر مستقیم فیلدهای {sorted(blocked)} با update() مجاز نیست؛ "
                "از change_status()/save() یا bulk_change_status() استفاده کنید."
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        """Block bulk_update() when it targets status, price or date fields."""
        blocked = ({"status"} | _RECALC_FIELDS) & set(fields)
        if blocked:
            raise ValueError(
                f"تغییر فیلدهای {sorted(blocked)} با bulk_update() مجاز نیست؛ "
                "از change_status()/save() استفاده کنید."
            )
        return super().bulk_update(objs, fields, *args, **kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        """Validate and price each booking before inserting them in bulk."""
        objs = list(objs)
        for obj in objs:
            obj._prepare_for_create()
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_change_status(self, new_status, *, by=None, reason=""):
        """
        Change the status of many bookings in a single UPDATE query.

        Only rows whose current status may legally move to ``new_status``
        (per ALLOWED_TRANSITIONS) are updated. The condition is part of the
        SQL statement itself, so it stays safe under concurrent writes.
        When canceling, the cancellation timestamp, actor and reason are
        recorded too. Returns the number of rows changed.
        """
        new_status = BookingStatus(new_status)
        allowed_from = [
            status for status, targets in ALLOWED_TRANSITIONS.items()
            if new_status in targets
        ]
        values = {"status": new_status, "updated_at": timezone.now()}
        if new_status == BookingStatus.CANCELED:
            values.update(
                cancelled_at=timezone.now(),
                cancelled_by=by,
                cancellation_reason=reason,
            )
        # Deliberately call the base QuerySet.update, not the guarded override
        # above, because this method is the sanctioned way to change status.
        return models.QuerySet.update(self.filter(status__in=allowed_from), **values)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Booking(models.Model):
   
    # The user who the booking is for.
    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    # The villa being booked.
    villa = models.ForeignKey(
        VILLA_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    # Stay period. check_out is exclusive, so a guest leaving on a date does
    # not conflict with another guest arriving on the same date.
    check_in = models.DateField()
    check_out = models.DateField()

    # Guest breakdown. Whether infants count toward capacity is controlled by
    # INFANTS_COUNT_TOWARD_CAPACITY.
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    infants = models.PositiveSmallIntegerField(default=0)

    # Current lifecycle state; see BookingStatus and ALLOWED_TRANSITIONS.
    status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )

    # Price snapshot. price_per_night is always copied from the villa and
    # final_price (= price_per_night x nights) is computed in save().
    # Both are editable=False, so they are read-only in ModelForms, the admin
    # and ModelSerializers.
    price_per_night = models.DecimalField(max_digits=14, decimal_places=2,
                                          editable=False,
                                          validators=[MinValueValidator(0)])
    final_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                      editable=False,
                                      validators=[MinValueValidator(0)])

    # Who created the booking and in what capacity (guest, host or admin).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bookings",
    )
    created_by_role = models.CharField(max_length=8, choices=CreatedByRole.choices,
                                       default=CreatedByRole.GUEST)

    # Cancellation audit trail, filled in when the booking is canceled.
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cancelled_bookings",
    )
    cancellation_reason = models.TextField(blank=True)

    # Automatic timestamps.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use the guarded QuerySet for all manager access.
    objects = BookingQuerySet.as_manager()

    # Status as loaded from the database; used in save() to detect illegal
    # direct assignments to ``status`` that bypass change_status().
    _original_status = None

    class Meta:
        """Database indexes and integrity constraints for Booking."""

        indexes: ClassVar[list] = [
            # Speeds up looking up a villa's bookings within a date range.
            models.Index(fields=["villa", "check_in", "check_out"],
                         name="booking_villa_dates_idx"),
            # Speeds up listing a guest's bookings, optionally by status.
            models.Index(fields=["guest", "status"], name="booking_guest_status_idx"),
        ]
        constraints: ClassVar[list] = [
            # The stay must end after it begins.
            models.CheckConstraint(
                condition=Q(check_out__gt=F("check_in")),
                name="booking_checkout_after_checkin",
            ),
            # At least one adult must be present.
            models.CheckConstraint(
                condition=Q(adults__gte=1),
                name="booking_at_least_one_adult",
            ),
            # Prices can never be negative.
            models.CheckConstraint(
                condition=Q(price_per_night__gte=0, final_price__gte=0),
                name="booking_amounts_non_negative",
            ),
            # A canceled booking must record when it was canceled.
            models.CheckConstraint(
                condition=~Q(status="canceled") | Q(cancelled_at__isnull=False),
                name="booking_canceled_has_timestamp",
            ),
            # Prevents double bookings: two active bookings for the same villa
            # cannot have overlapping [check_in, check_out) date ranges.
            # Requires PostgreSQL and the btree_gist extension
            # (BtreeGistExtension in a migration).
            ExclusionConstraint(
                name=OVERLAP_CONSTRAINT_NAME,
                expressions=[
                    (
                        Func(
                            F("check_in"),
                            F("check_out"),
                            Value("[)"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("villa", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
        ]

    # ---------- Loading and status tracking ----------

    @classmethod
    def from_db(cls, db, field_names, values):
        """Remember the status loaded from the DB so illegal changes can be detected."""
        # Reads from __dict__ instead of self.status so that deferred fields
        # (.only()/.defer()) do not trigger an extra query.
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.__dict__.get("status")
        return instance

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        """Reload from the DB and re-sync the remembered original status."""
        super().refresh_from_db(using=using, fields=fields, **kwargs)
        if fields is None or "status" in fields:
            self._original_status = self.__dict__.get("status")

    def __str__(self):
        return f"Booking #{self.pk} | {self.villa_id} | {self.check_in} → {self.check_out}"

    # ---------- Villa access helpers ----------

    def _get_villa(self):
        """Return the related villa, or None if it is unset or does not exist."""
        if not self.villa_id:
            return None
        try:
            return self.villa
        except ObjectDoesNotExist:
            return None

    @staticmethod
    def _villa_is_bookable(villa) -> bool:
        """
        Check whether the villa can be booked.

        Uses the first attribute from VILLA_BOOKABLE_FIELDS that exists on the
        villa (calling it if it is a method). Defaults to True if none exist.
        """
        for name in VILLA_BOOKABLE_FIELDS:
            if hasattr(villa, name):
                value = getattr(villa, name)
                return bool(value() if callable(value) else value)
        return True

    # ---------- Calculations ----------

    @property
    def total_guests(self) -> int:
        """Number of guests that count toward capacity (adults + children, plus infants if configured)."""
        total = self.adults + self.children
        if INFANTS_COUNT_TOWARD_CAPACITY:
            total += self.infants
        return total

    def calculate_nights(self) -> int:
        """Return the number of nights, or 0 for a missing or invalid range (never negative)."""
        if self.check_in and self.check_out:
            return max((self.check_out - self.check_in).days, 0)
        return 0

    @property
    def nights(self) -> int:
        """Number of nights, derived from the dates rather than stored."""
        return self.calculate_nights()

    def calculate_final_price(self) -> Decimal:
        """Return the total price: price per night x number of nights, rounded to cents."""
        return (_dec(self.price_per_night) * self.calculate_nights()).quantize(CENT)

    def recalculate_prices(self):
        """Refresh ``final_price`` from the current price and dates."""
        self.final_price = self.calculate_final_price()

    def _fill_price_from_villa(self):
        """Copy the nightly price from the villa, ignoring any client-supplied value."""
        villa = self._get_villa()
        if villa is None:
            return
        price = getattr(villa, VILLA_PRICE_FIELD, None)
        if price is None:
            raise ValidationError(
                {"villa": "قیمت هر شب برای این ویلا تعریف نشده است."}
            )
        self.price_per_night = _dec(price).quantize(CENT)

    # ---------- Validation ----------

    def clean(self):
        """Run model-level validation and raise all collected errors together."""
        errors = {}
        errors.update(self._validate_dates())
        errors.update(self._validate_villa())
        if errors:
            raise ValidationError(errors)

    def _validate_dates(self) -> dict:
        """Check that check-out is after check-in and that new bookings are not in the past."""
        errors = {}
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            errors["check_out"] = "تاریخ خروج باید بعد از تاریخ ورود باشد."
        if self._state.adding and self.check_in and self.check_in < local_today():
            errors["check_in"] = "تاریخ ورود نمی‌تواند در گذشته باشد."
        return errors

    def _validate_villa(self) -> dict:
        """Check that the villa exists, is bookable (for new bookings) and fits the guest count."""
        if not self.villa_id:
            return {}

        villa = self._get_villa()
        if villa is None:
            return {"villa": "ویلای انتخاب‌شده وجود ندارد."}

        errors = {}
        if self._state.adding and not self._villa_is_bookable(villa):
            errors["villa"] = "این ویلا در حال حاضر قابل رزرو نیست."

        max_guests = getattr(villa, VILLA_CAPACITY_FIELD, None)
        if max_guests is not None and self.total_guests > max_guests:
            errors["adults"] = "تعداد مهمان‌ها از ظرفیت ویلا بیشتر است."
        return errors

    def _prepare_for_create(self):
        
        if self.status != INITIAL_STATUS:
            raise ValidationError(
                {"status": f"رزرو جدید باید با وضعیت «{INITIAL_STATUS.label}» ساخته شود."}
            )
        self._fill_price_from_villa()
        self.recalculate_prices()
        self.full_clean(validate_constraints=False)

    # ---------- Status handling ----------

    def can_transition_to(self, new_status) -> bool:
        """Return True if moving from the current status to ``new_status`` is allowed."""
        return new_status in ALLOWED_TRANSITIONS.get(self.status, set())

    def change_status(self, new_status, *, by=None, reason=""):
        
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"تغییر وضعیت از «{self.get_status_display()}» "
                f"به «{BookingStatus(new_status).label}» مجاز نیست."
            )
        self.status = new_status
        if new_status == BookingStatus.CANCELED:
            self.cancelled_at = timezone.now()
            self.cancelled_by = by
            self.cancellation_reason = reason

    def save(self, *args, **kwargs):
        
        if self._state.adding:
            self._prepare_for_create()
        # Guard against bypassing the state machine via direct assignment.
        elif (
            self._original_status is not None
            and self.status != self._original_status
            and self.status not in ALLOWED_TRANSITIONS.get(self._original_status, set())
        ):
            raise ValidationError(
                f"تغییر وضعیت از «{self._original_status}» به «{self.status}» مجاز نیست."
            )

        self.recalculate_prices()

        # If update_fields is given and non-empty, make sure the recalculated
        # price and updated_at are saved as well.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and len(update_fields) > 0:
            kwargs["update_fields"] = set(update_fields) | _COMPUTED_FIELDS

        super().save(*args, **kwargs)
        self._original_status = self.status