# ============================================================
# Imports
# ============================================================

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html

from .models import Booking, BookingStatus, Payment, Villa

# ============================================================
# Inline For Booking Payments
# ============================================================

class PaymentInline(admin.TabularInline):

    model = Payment

    extra = 0

    fields = (
        "amount",
        "status",
        "transaction_id",
        "payment_gateway",
        "paid_at",
        "created_at",
    )

    readonly_fields = ("created_at",)

    can_delete = False

    show_change_link = True

# ============================================================
# Villa Management Panel Settings
# ============================================================

@admin.register(Villa)
class VillaAdmin(admin.ModelAdmin):

    # --------------------------------------------------------
    # Fields Displayed In The Villa List
    # --------------------------------------------------------

    list_display = (
        "id",
        "title",
        "host",
        "capacity",
        "base_price",
        "cleaning_fee",
        "service_fee",
        "created_at",
    )

    # --------------------------------------------------------
    # Fields Used To Filter Villas
    # --------------------------------------------------------

    list_filter = ("created_at",)

    # --------------------------------------------------------
    # Searchable Fields
    # --------------------------------------------------------

    search_fields = (
        "title",
        "host__username",
        "host__email",
    )

    # --------------------------------------------------------
    # Host Selection With Search Capability
    # --------------------------------------------------------

    autocomplete_fields = ("host",)

    # --------------------------------------------------------
    # Read-Only Fields
    # --------------------------------------------------------

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    # --------------------------------------------------------
    # Villa Display Order
    # --------------------------------------------------------

    ordering = ("-created_at",)

    # ========================================================
    # Categorization Of Fields In The Villa Management Form
    # ========================================================

    fieldsets = (

        # << Basic Villa Information >>
        (None, {
            "fields": (
                "host",
                "title",
                "capacity",
            )
        }),

        ("قیمت‌گذاری", {
            "fields": (
                "base_price",
                "cleaning_fee",
                "service_fee",
                "extra_guest_threshold",
                "extra_guest_fee",
            )
        }),

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
        }),
    )


# ============================================================
# Custom Booking Status Filter
# ============================================================

class BookingStatusFilter(admin.SimpleListFilter):

    title = "وضعیت"

    parameter_name = "status"

    # --------------------------------------------------------
    # Status Filter Options
    # --------------------------------------------------------

    def lookups(self, request, model_admin):
        return BookingStatus.choices

    # --------------------------------------------------------
    # Applying a filter to a QuerySet
    # --------------------------------------------------------

    def queryset(self, request, queryset):

        if self.value():
            return queryset.filter(
                status=self.value()
            )

        return queryset


# ============================================================
# Custom Booking Management Form
# ============================================================

class BookingAdminForm(forms.ModelForm):

    class Meta:

        model = Booking

        # << Fields Included In The Reservation Management Form >>
        fields = (
            "villa",
            "guest",
            "created_by",
            "check_in",
            "check_out",
            "guests_count",
            "status",
            "expires_at",
            "nightly_price_snapshot",
            "base_price",
            "cleaning_fee",
            "service_fee",
            "extra_guest_fee",
            "discount",
            "final_price",
            "villa_title_snapshot",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
        )

    # ========================================================
    # Validation Of Booking Status Change
    # ========================================================

    def clean_status(self):

        # << The New Status Selected By The User >> 
        new_status = self.cleaned_data["status"]

        if self.instance.pk is None:
            return new_status

        # ----------------------------------------------------
        # Previous Reservation Status
        # ----------------------------------------------------

        old_status = self.instance.status

        if old_status == new_status:
            return new_status

        # ----------------------------------------------------
        # Review Of The Permissibility Of Status Transfer
        # ----------------------------------------------------

        if not self.instance.can_transition_to(new_status):
            raise ValidationError(
                f"انتقال وضعیت از «{self.instance.get_status_display()}» "
                f"به «{dict(BookingStatus.choices).get(new_status, new_status)}» "
                "مجاز نیست."
            )

        return new_status


# ============================================================
# Reservation Management Panel Settings
# ============================================================

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    form = BookingAdminForm

    # --------------------------------------------------------
    # Fields Displayed In The Reservations List
    # --------------------------------------------------------

    list_display = (
        "id",
        "villa_title_snapshot",
        "guest",
        "check_in",
        "check_out",
        "guests_count",
        "colored_status",
        "final_price",
        "created_at",
    )

    # --------------------------------------------------------
    # Reservation List Filters
    # --------------------------------------------------------

    list_filter = (
        BookingStatusFilter,
        "created_at",
        "check_in",
    )

    # --------------------------------------------------------
    # Searchable Fields
    # --------------------------------------------------------

    search_fields = (
        "villa__title",
        "villa_title_snapshot",
        "guest__username",
        "guest__email",
        "created_by__username",
    )

    # --------------------------------------------------------
    # Searchable ForeignKey Fields
    # --------------------------------------------------------

    autocomplete_fields = (
        "villa",
        "guest",
        "created_by",
        "cancelled_by",
    )

    # --------------------------------------------------------
    # Read-Only Fields
    # --------------------------------------------------------

    readonly_fields = (
        "villa_title_snapshot",
        "nightly_price_snapshot",
        "cancelled_at",
        "cancelled_by",
        "created_at",
        "updated_at",
    )

    # --------------------------------------------------------
    # Quick Selection Based On Arrival Date
    # --------------------------------------------------------

    date_hierarchy = "check_in"

    # --------------------------------------------------------
    # Reservation Display Order
    # --------------------------------------------------------

    ordering = ("-created_at",)

    # --------------------------------------------------------
    # View Payments For Each Reservation
    # --------------------------------------------------------

    inlines = (PaymentInline,)

    # --------------------------------------------------------
    # Custom Actions Related To Bookings
    # --------------------------------------------------------

    actions = (
        "mark_as_confirmed",
        "mark_as_cancelled",
    )

    # ========================================================
    # Categorizing Reservation Form Fields
    # ========================================================

    fieldsets = (

        # ----------------------------------------------------
        # Basic Booking Information
        # ----------------------------------------------------

        (None, {
            "fields": (
                "villa",
                "villa_title_snapshot",
                "guest",
                "created_by",
                "status",
            )
        }),

        # ----------------------------------------------------
        # Booking Period
        # ----------------------------------------------------

        ("بازه‌ی رزرو", {
            "fields": (
                "check_in",
                "check_out",
                "guests_count",
                "expires_at",
            )
        }),

        # ----------------------------------------------------
        # Pricing Information
        # ----------------------------------------------------

        ("قیمت‌ها", {
            "fields": (
                "nightly_price_snapshot",
                "base_price",
                "cleaning_fee",
                "service_fee",
                "extra_guest_fee",
                "discount",
                "final_price",
            )
        }),

        # ----------------------------------------------------
        # Reservation Cancellation Information
        # ----------------------------------------------------

        ("لغو رزرو", {

            "fields": (
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
            ),

            "classes": ("collapse",),
        }),

        # ----------------------------------------------------
        # Creation And Last Edit Dates
        # ----------------------------------------------------

        ("تاریخ‌ها", {
            "fields": (
                "created_at",
                "updated_at",
            ),
        }),
    )

    # ========================================================
    # Color Display Of Reservation Status
    # ========================================================

    @admin.display(description="وضعیت")
    def colored_status(self, obj):

        # << Color Display Of Reservation Status >>
        colors = {
            BookingStatus.PENDING: "#f59e0b",
            BookingStatus.CONFIRMED: "#16a34a",
            BookingStatus.CANCELLED: "#dc2626",
            BookingStatus.EXPIRED: "#6b7280",
        }

        # << Get Current Status Color >>
        color = colors.get(
            obj.status,
            "#000000"
        )

        # << Display Status With The Assigned Color >>
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    # ========================================================
    # Action To Confirm Selected Reservations
    # ========================================================

    @admin.action(description="تأیید رزروهای انتخاب‌شده")
    def mark_as_confirmed(self, request, queryset):

        updated = 0

        skipped = 0

        for booking in queryset:

            if booking.can_transition_to(
                BookingStatus.CONFIRMED
            ):

                booking.status = BookingStatus.CONFIRMED

                booking.save(
                    update_fields=[
                        "status",
                        "period",
                        "updated_at",
                    ]
                )

                updated += 1

            else:
                skipped += 1

        self.message_user(
            request,
            f"{updated} رزرو تأیید شد.",
            level=messages.SUCCESS,
        )

        if skipped:
            self.message_user(
                request,
                f"{skipped} رزرو به‌دلیل وضعیت فعلی‌شان تأیید نشدند.",
                level=messages.WARNING,
            )

    # ========================================================
    # Action To Cancel Selected Reservations
    # ========================================================

    @admin.action(description="لغو رزروهای انتخاب‌شده")
    def mark_as_cancelled(self, request, queryset):

        updated = 0

        skipped = 0

        now = timezone.now()

        for booking in queryset:

            if booking.can_transition_to(
                BookingStatus.CANCELLED
            ):

                booking.status = BookingStatus.CANCELLED

                booking.cancelled_at = now

                booking.cancelled_by = request.user

                booking.save(
                    update_fields=[
                        "status",
                        "period",
                        "cancelled_at",
                        "cancelled_by",
                        "updated_at",
                    ]
                )

                updated += 1

            else:
                skipped += 1

        self.message_user(
            request,
            f"{updated} رزرو لغو شد."
        )

        if skipped:
            self.message_user(
                request,
                f"{skipped} رزرو به‌دلیل وضعیت فعلی‌شان لغو نشدند.",
                level="warning",
            )


# ============================================================
# Payment Management Panel Settings
# ============================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    # --------------------------------------------------------
    # Fields Displayed In The Payments List
    # --------------------------------------------------------

    list_display = (
        "id",
        "booking",
        "amount",
        "status",
        "payment_gateway",
        "transaction_id",
        "paid_at",
        "created_at",
    )

    # --------------------------------------------------------
    # Payment Filters
    # --------------------------------------------------------

    list_filter = (
        "status",
        "payment_gateway",
        "created_at",
    )

    # --------------------------------------------------------
    # Searchable Fields
    # --------------------------------------------------------

    search_fields = (
        "transaction_id",
        "booking__villa_title_snapshot",
        "booking__guest__username",
    )

    # --------------------------------------------------------
    # Reservation Selection With Search Capability
    # --------------------------------------------------------

    autocomplete_fields = ("booking",)

    # --------------------------------------------------------
    # Read-Only Fields
    # --------------------------------------------------------

    readonly_fields = ("created_at",)

    # --------------------------------------------------------
    #  Payment Display Order 
    # --------------------------------------------------------

    ordering = ("-created_at",)
