# properties/admin.py
from django.contrib import admin
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin
from unfold.admin import ModelAdmin, StackedInline

from .models import (
    AccommodationType,
    Amenity,
    AttributeDefinition,
    CancellationPolicy,
    CancellationRule,
    Category,
    City,
    Country,
    County,
    District,
    PermissionRule,
    Property,
    PropertyImage,
    PropertyLocation,
    PropertyRule,
    PropertyVerification,
    Province,
    QuantityRule,
    RuralDistrict,
    TimeRule,
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = (
        "image_preview",
        "image",
        "alt_text",
        "is_cover",
        "order",
    )
    readonly_fields = ("image_preview",)
    verbose_name = "تصویر"
    verbose_name_plural = "تصاویر"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 6px;" />',
                obj.image.url,
            )
        return "—"

    image_preview.short_description = "پیش‌نمایش"


class CancellationRuleInline(admin.TabularInline):
    model = CancellationRule
    extra = 0
    fields = (
        "priority",
        "hours_before_checkin",
        "hours_before_checkin_max",
        "refund_percentage",
        "charge_first_night",
        "note",
    )
    ordering = ("priority",)

    verbose_name = "قانون لغو"
    verbose_name_plural = "قوانین لغو"


class PropertyVerificationInline(StackedInline):
    model = PropertyVerification
    max_num = 1
    can_delete = False
    readonly_fields = (
        "created_at",
        "updated_at",
    )


class PropertyLocationInline(StackedInline):
    model = PropertyLocation
    autocomplete_fields = ("city",)
    max_num = 1


class PermissionRuleInline(StackedInline):
    model = PermissionRule
    max_num = 1


class TimeRuleInline(StackedInline):
    model = TimeRule
    max_num = 1


class QuantityRuleInline(StackedInline):
    model = QuantityRule
    max_num = 1


class PropertyRuleInline(StackedInline):
    model = PropertyRule
    extra = 1


@admin.register(AccommodationType)
class AccommodationTypeAdmin(ModelAdmin):
    list_display = (
        "name",
        "name_en",
        "code",
        "parent",
        "sort_order",
        "is_active",
    )
    list_display_links = ("name",)
    list_editable = (
        "sort_order",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "name",
        "name_en",
        "code",
    )
    autocomplete_fields = ("parent",)
    list_select_related = ("parent",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "اطلاعات نوع اقامتگاه",
            {
                "fields": (
                    "name",
                    "name_en",
                    "code",
                    "description",
                )
            },
        ),
        (
            "ساختار و نمایش",
            {
                "fields": (
                    "parent",
                    "sort_order",
                    "is_active",
                )
            },
        ),
        (
            "تاریخ‌ها",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.append("code")
        return tuple(fields)


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(ModelAdmin):
    list_display = (
        "code",
        "is_active",
        "created_by",
        "created_at",
    )
    list_display_links = ("code",)
    list_filter = ("is_active",)
    search_fields = ("code",)
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "تعریف ویژگی",
            {
                "fields": (
                    "code",
                    "is_active",
                )
            },
        ),
        (
            "اطلاعات ثبت",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.append("code")
        return tuple(fields)


@admin.register(Property)
class PropertyAdmin(ModelAdminJalaliMixin, ModelAdmin):
    filter_horizontal = ("amenities",)
    autocomplete_fields = ("owner",)
    list_select_related = ("owner",)
    inlines = (
        PropertyRuleInline,
        PropertyVerificationInline,
        PropertyLocationInline,
        PropertyImageInline,
    )
    list_display = (
        "title",
        "owner",
        "accommodation_type",
        "status",
        "is_active",
        "verification_status",
        "max_guests",
        "nightly_price",
        "created_at",
    )
    list_filter = (
        "accommodation_type",
        "status",
        "is_active",
        "verification_status",
    )
    search_fields = (
        "title",
        "description",
        "slug",
        "owner__email",
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "اطلاعات هویتی",
            {
                "fields": (
                    "owner",
                    "title",
                    "slug",
                    "description",
                    "accommodation_type",
                )
            },
        ),
        (
            "ظرفیت و مشخصات فیزیکی",
            {
                "fields": (
                    "max_guests",
                    "bedrooms",
                    "beds",
                    "bathrooms",
                    "toilets",
                    "building_area",
                    "land_area",
                    "floor",
                )
            },
        ),
        ("قیمت", {"fields": ("nightly_price",)}),
        ("امکانات رفاهی", {"fields": ("amenities",)}),
        ("وضعیت", {"fields": ("status", "is_active", "verification_status")}),
        ("تاریخ‌ها", {"fields": ("created_at", "updated_at", "published_at")}),
    )


@admin.register(Country)
class CountryAdmin(ModelAdmin):
    list_display = (
        "name",
        "code",
    )
    search_fields = (
        "name",
        "code",
    )


@admin.register(Province)
class ProvinceAdmin(ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = (
        "name",
        "code",
    )
    list_filter = ("country",)
    autocomplete_fields = ("country",)


@admin.register(County)
class CountyAdmin(ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = (
        "name",
        "code",
    )
    list_filter = ("province",)
    autocomplete_fields = ("province",)


@admin.register(District)
class DistrictAdmin(ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = (
        "name",
        "code",
    )
    list_filter = ("county",)
    autocomplete_fields = ("county",)


@admin.register(RuralDistrict)
class RuralDistrictAdmin(ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = (
        "name",
        "code",
    )
    list_filter = ("district",)
    autocomplete_fields = ("district",)


@admin.register(City)
class CityAdmin(ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = ("name", "code", "province", "county", "district")
    list_filter = ("province", "county", "district")
    autocomplete_fields = (
        "province",
        "county",
        "district",
    )


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "is_active")
    list_filter = ("is_active",)


@admin.register(Amenity)
class AmenityAdmin(ModelAdmin):
    search_fields = ("name",)
    list_display = (
        "name",
        "category",
        "is_active",
    )
    list_filter = (
        "category",
        "is_active",
    )
    autocomplete_fields = ("category",)


@admin.register(CancellationPolicy)
class CancellationPolicyAdmin(ModelAdmin):
    inlines = (CancellationRuleInline,)
    search_fields = (
        "title",
        "property_obj__title",
    )
    list_display = (
        "title",
        "property_obj",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    autocomplete_fields = ("property_obj",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(PropertyVerification)
class PropertyVerificationAdmin(ModelAdmin):
    search_fields = ("property_obj__title",)
    list_display = (
        "property_obj",
        "status",
        "verified_at",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "verified_at",
    )
    autocomplete_fields = ("property_obj",)
    fieldsets = (
        ("اطلاعات ملک", {"fields": ("property_obj",)}),
        ("وضعیت تأیید", {"fields": ("status", "verified_at")}),
        ("دلیل رد و یادداشت", {"fields": ("rejection_reason", "admin_note")}),
        ("تاریخ‌ها", {"fields": ("created_at", "updated_at")}),
    )
