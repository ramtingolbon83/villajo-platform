from rest_framework import serializers

from .models import (
    Amenity,
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


class PropertyListSerializer(serializers.ModelSerializer):
    property_type_display = serializers.CharField(
        source="get_property_type_display", read_only=True
    )

    class Meta:
        model = Property
        fields = (
            "id",
            "title",
            "property_type",
            "property_type_display",
            "max_guests",
            "bedrooms",
            "beds",
            "bathrooms",
            "building_area",
            "land_area",
        )


class AmenityNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = (
            "id",
            "name",
            "slug",
        )
        read_only_fields = ("id",)


class PropertyDetailSerializer(serializers.ModelSerializer):
    property_type_display = serializers.CharField(
        source="get_property_type_display", read_only=True
    )

    amenities = AmenityNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "property_type",
            "property_type_display",
            "amenities",
            "max_guests",
            "bedrooms",
            "beds",
            "bathrooms",
            "toilets",
            "building_area",
            "land_area",
            "floor",
            "status",
            "verification_status",
            "created_at",
            "updated_at",
            "published_at",
        )


class PropertyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property

        fields = (
            "title",
            "description",
            "property_type",
            "amenities",
            "max_guests",
            "bedrooms",
            "beds",
            "bathrooms",
            "toilets",
            "building_area",
            "land_area",
            "floor",
        )


class PropertyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = (
            "title",
            "description",
            "property_type",
            "amenities",
            "max_guests",
            "bedrooms",
            "beds",
            "bathrooms",
            "toilets",
            "floor",
        )


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code", "slug")
        read_only_fields = ("id", "slug")


class ProvinceSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = Province
        fields = ("id", "name", "code", "slug", "country", "country_name")
        read_only_fields = ("id", "slug")


class CountySerializer(serializers.ModelSerializer):
    class Meta:
        model = County
        fields = ("id", "name", "code", "slug", "province")
        read_only_fields = ("id", "slug")


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ("id", "name", "code", "slug", "county")
        read_only_fields = (
            "id",
            "slug",
        )


class RuralDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuralDistrict
        fields = ("id", "name", "code", "slug", "district")
        read_only_fields = (
            "id",
            "slug",
        )


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name", "code", "slug", "province", "county", "district")
        read_only_fields = (
            "id",
            "slug",
        )

    def validate(self, attrs):
        province = attrs.get("province") or getattr(self.instance, "province", None)
        county = attrs.get("county") or getattr(self.instance, "county", None)
        district = attrs.get("district") or getattr(self.instance, "district", None)
        if county and province and county.province_id != province.id:
            raise serializers.ValidationError("شهرستان متعلق به این استان نیست.")
        if district and county and district.county_id != county.id:
            raise serializers.ValidationError("بخش متعلق به این شهرستان نیست.")
        return attrs

class PropertyLocationSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = PropertyLocation
        fields = (
            "id",
            "property_obj",
            "city",
            "city_name",
            "address",
            "postal_code",
            "latitude",
            "longitude",
        )
        read_only_fields = ("id",)

    def validate_property_obj(self, value):
        if self.instance and self.instance.property_obj != value:
            raise serializers.ValidationError("تغییر ملک مجاز نیست.")
        request = self.context["request"]
        if value.owner != request.user and not request.user.is_staff:
            raise serializers.ValidationError("این ملک متعلق به شما نیست.")
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "is_active", "slug")
        read_only_fields = ("id", "slug")


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "category", "name", "slug", "is_active")
        read_only_fields = ("id", "slug")


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = (
            "id",
            "property_obj",
            "image",
            "alt_text",
            "is_cover",
            "order",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_property_obj(self, value):
        if self.instance and self.instance.property_obj != value:
            raise serializers.ValidationError("تغییر ملک مجاز نیست.")
        request = self.context["request"]
        if value.owner != request.user and not request.user.is_staff:
            raise serializers.ValidationError("این ملک متعلق به شما نیست.")
        return value

    def validate_image(self, value):
        max_size = 5 * 1024 * 1024  # 5 MB(MiB)
        if value.size > max_size:
            raise serializers.ValidationError("حجم تصویر باید کمتر از ۵ مگابایت باشد.")
        return value


class PropertyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyRule
        fields = ("id", "rule_key", "property_obj", "amenity")
        read_only_fields = ("id",)


class PermissionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionRule
        fields = ("id", "allowed", "rule")
        read_only_fields = ("id",)


class TimeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeRule
        fields = ("id", "start_time", "end_time", "rule")
        read_only_fields = ("id",)


class QuantityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuantityRule
        fields = ("id", "value", "rule")
        read_only_fields = ("id",)


class CancellationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CancellationPolicy
        fields = (
            "id",
            "title",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "property_obj",
        )
        read_only_fields = (
            "id",
            "property_obj",
            "created_at",
            "updated_at",
        )


class CancellationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancellationRule
        fields = (
            "id",
            "hours_before_checkin",
            "hours_before_checkin_max",
            "refund_percentage",
            "charge_first_night",
            "note",
            "priority",
            "policy",
        )
        read_only_fields = ("id",)


class PropertyVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyVerification
        fields = (
            "id",
            "status",
            "verified_at",
            "rejection_reason",
            "admin_note",
            "created_at",
            "updated_at",
            "property_obj",
        )
        read_only_fields = (
            "id",
            "status",
            "verified_at",
            "created_at",
            "updated_at",
            "property_obj",
        )
