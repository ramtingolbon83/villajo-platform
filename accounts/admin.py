from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from jalali_date.admin import ModelAdminJalaliMixin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import (
    Account,
    AuditEvent,
    AvailabilitySlot,
    Reservation,
    Task,
    WorkTime,
)


class AccountCreationForm(UserCreationForm):
    class Meta:
        model = Account
        fields = ("email", "role")


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = Account
        fields = "__all__"


@admin.register(Account)
class AccountAdmin(ModelAdminJalaliMixin, BaseUserAdmin, ModelAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    change_password_form = AdminPasswordChangeForm

    ordering = ("email",)
    list_display = ("email", "role", "is_active", "is_verified", "is_staff")
    list_filter = ("role", "is_active", "is_verified", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone_number")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("اطلاعات شخصی", {"fields": ("first_name", "last_name", "phone_number")}),
        (
            "دسترسی",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_verified",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("تاریخ‌ها", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role"),
            },
        ),
    )


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdminJalaliMixin, ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_id", "ip_address")
    list_filter = ("action", "object_type")
    search_fields = ("actor__email", "action", "object_type", "object_id")
    list_select_related = ("actor",)

    # The log is append-only: view only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(ModelAdminJalaliMixin, ModelAdmin):
    list_display = ("property_obj", "starts_at", "ends_at", "status")
    list_filter = ("status",)
    search_fields = ("property_obj__title", "note")
    autocomplete_fields = ("property_obj",)
    list_select_related = ("property_obj",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Reservation)
class ReservationAdmin(ModelAdminJalaliMixin, ModelAdmin):
    list_display = ("customer", "property_obj", "starts_at", "ends_at", "guest_count", "status")
    list_filter = ("status",)
    search_fields = ("customer__email", "property_obj__title")
    autocomplete_fields = ("customer", "property_obj")
    list_select_related = ("customer", "property_obj")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Task)
class TaskAdmin(ModelAdminJalaliMixin, ModelAdmin):
    list_display = ("title", "property_obj", "assigned_to", "created_by", "status", "due_at")
    list_filter = ("status",)
    search_fields = ("title", "assigned_to__email", "created_by__email")
    autocomplete_fields = ("property_obj", "assigned_to", "created_by")
    list_select_related = ("property_obj", "assigned_to", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkTime)
class WorkTimeAdmin(ModelAdminJalaliMixin, ModelAdmin):
    list_display = ("employee", "task", "started_at", "ended_at", "approved")
    list_filter = ("approved",)
    search_fields = ("employee__email", "task__title", "note")
    autocomplete_fields = ("employee", "task")
    list_select_related = ("employee", "task")
    readonly_fields = ("created_at", "updated_at")