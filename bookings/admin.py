from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import ACTIVE_STATUSES, Booking, BookingStatus, CreatedByRole


class BookingAdminForm(forms.ModelForm):

    class Meta:
        model = Booking
        fields = "__all__"

    def clean(self):
        
        cleaned = super().clean()
        villa = cleaned.get("villa")
        check_in = cleaned.get("check_in")
        check_out = cleaned.get("check_out")

        # Only new bookings can change dates/villa from the admin; existing
        # ones have those fields read-only. Skip if the base checks failed.
        if self.instance.pk or not (villa and check_in and check_out):
            return cleaned
        if check_out <= check_in:
            return cleaned

        conflict = Booking.objects.filter(
            villa=villa,
            status__in=ACTIVE_STATUSES,
            check_in__lt=check_out,
            check_out__gt=check_in,
        ).exists()
        if conflict:
            raise ValidationError(
                "این ویلا در بازه انتخاب‌شده رزرو فعال دیگری دارد."
            )
        return cleaned


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    form = BookingAdminForm

    list_display = (
        "id",
        "villa",
        "guest",
        "check_in",
        "check_out",
        "nights_display",
        "status",
        "final_price",
        "created_by_role",
        "created_at",
    )
    list_filter = ("status", "created_by_role", "check_in", "created_at")
    search_fields = ("=id",)  # add e.g. "guest__phone" to match your user model
    date_hierarchy = "check_in"
    ordering = ("-created_at",)
    list_select_related = ("villa", "guest")
    list_per_page = 25

    # Raw-ID widgets avoid loading every user/villa into a dropdown.
    raw_id_fields = ("guest", "villa")

    actions = ("cancel_bookings", "complete_bookings")

    add_fieldsets = (
        (None, {"fields": ("guest", "villa", "check_in", "check_out")}),
        ("مهمان‌ها", {"fields": ("adults", "children", "infants")}),
    )

    change_fieldsets = (
        (None, {"fields": ("guest", "villa", "check_in", "check_out")}),
        ("مهمان‌ها", {"fields": ("adults", "children", "infants")}),
        ("وضعیت و قیمت", {
            "fields": ("status", "price_per_night", "final_price"),
        }),
        ("ایجادکننده", {"fields": ("created_by", "created_by_role")}),
        ("لغو", {
            "fields": ("cancelled_at", "cancelled_by", "cancellation_reason"),
        }),
        ("زمان‌ها", {"fields": ("created_at", "updated_at")}),
    )

    # ---------- Form layout ----------

    def get_fieldsets(self, request, obj=None):
        return self.change_fieldsets if obj else self.add_fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return (
            "guest", "villa", "check_in", "check_out",
            "status", "price_per_night", "final_price",
            "created_by", "created_by_role",
            "cancelled_at", "cancelled_by", "cancellation_reason",
            "created_at", "updated_at",
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "guest", "villa", "created_by", "cancelled_by"
        )

    # ---------- Display helpers ----------

    @admin.display(description="تعداد شب")
    def nights_display(self, obj):
        return obj.nights

    # ---------- Saving ----------

    def save_model(self, request, obj, form, change):
        if not change:
            # Never taken from the form; always the logged-in admin user.
            obj.created_by = request.user
            obj.created_by_role = CreatedByRole.ADMIN
        super().save_model(request, obj, form, change)

    # ---------- Permissions ----------

    def has_delete_permission(self, request, obj=None):
        # Bookings are financial records; cancel them instead of deleting.
        return False

    # ---------- Actions (single entry point for status changes) ----------

    @admin.action(description="لغو رزروهای انتخاب‌شده")
    def cancel_bookings(self, request, queryset):
        changed = queryset.bulk_change_status(
            BookingStatus.CANCELED,
            by=request.user,
            reason="لغو توسط ادمین",
        )
        self._report(request, queryset, changed)

    @admin.action(description="تکمیل‌شده کردن رزروهای انتخاب‌شده")
    def complete_bookings(self, request, queryset):
        changed = queryset.bulk_change_status(BookingStatus.COMPLETED)
        self._report(request, queryset, changed)

    def _report(self, request, queryset, changed):
        total = queryset.count()
        skipped = total - changed
        if changed:
            self.message_user(
                request, f"وضعیت {changed} رزرو تغییر کرد.", messages.SUCCESS
            )
        if skipped:
            self.message_user(
                request,
                f"{skipped} رزرو به‌دلیل مجاز نبودن انتقال وضعیت تغییر نکرد.",
                messages.WARNING,
            )