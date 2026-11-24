from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly

from accounts.models import Account
from properties.models import (
    Amenity,
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
    Province,
    QuantityRule,
    RuralDistrict,
    TimeRule,
)
from properties.permission import IsAdminOrReadOnly, IsPropertyOwnerOrReadOnly, is_admin
from properties.serializers import (
    AmenitySerializer,
    CategorySerializer,
    CitySerializer,
    CountrySerializer,
    CountySerializer,
    DistrictSerializer,
    PermissionRuleSerializer,
    PropertyCreateSerializer,
    PropertyDetailSerializer,
    PropertyImageSerializer,
    PropertyListSerializer,
    PropertyLocationSerializer,
    PropertyRuleSerializer,
    PropertyUpdateSerializer,
    ProvinceSerializer,
    QuantityRuleSerializer,
    RuralDistrictSerializer,
    TimeRuleSerializer,
)


class PropertyViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly, IsPropertyOwnerOrReadOnly)

    def get_queryset(self):
        queryset = Property.objects.prefetch_related("amenities")
        user = self.request.user

        if is_admin(user):
            return queryset

        # Public rule: only published AND active properties are visible
        public = Q(status="published", is_active=True)
        if user.is_authenticated and user.role == Account.Role.OWNER:
            return queryset.filter(public | Q(owner=user))
        return queryset.filter(public)

    def get_serializer_class(self):
        return {
            "list": PropertyListSerializer,
            "retrieve": PropertyDetailSerializer,
            "create": PropertyCreateSerializer,
        }.get(self.action, PropertyUpdateSerializer)

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == Account.Role.OWNER:
            # Any "owner" value sent by the client is ignored
            serializer.save(owner=user)
        elif is_admin(user):
            if not serializer.validated_data.get("owner"):
                raise ValidationError(
                    {"owner": "Required when an admin creates a property."}
                )
            serializer.save()
        else:
            raise PermissionDenied("Only owners and admins can create properties.")


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = (IsAdminOrReadOnly,)


class ProvinceViewSet(viewsets.ModelViewSet):
    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer
    filterset_fields = ("country",)
    permission_classes = (IsAdminOrReadOnly,)


class CountyViewSet(viewsets.ModelViewSet):
    queryset = County.objects.all()
    serializer_class = CountySerializer
    filterset_fields = ("province",)
    permission_classes = (IsAdminOrReadOnly,)


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.all()
    serializer_class = DistrictSerializer
    filterset_fields = ("county",)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class RuralDistrictViewSet(viewsets.ModelViewSet):
    queryset = RuralDistrict.objects.all()
    serializer_class = RuralDistrictSerializer
    filterset_fields = ("district",)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    filterset_fields = ("province", "county", "district")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class PropertyLocationViewSet(viewsets.ModelViewSet):
    queryset = PropertyLocation.objects.select_related(
        "city",
        "property_obj",
    )
    serializer_class = PropertyLocationSerializer
    filterset_fields = ("city", "property_obj")
    permission_classes = (IsAuthenticatedOrReadOnly, IsPropertyOwnerOrReadOnly)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)


class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    filterset_fields = ("category",)
    permission_classes = (IsAdminOrReadOnly,)


class PropertyImageViewSet(viewsets.ModelViewSet):
    queryset = PropertyImage.objects.select_related("property_obj")
    serializer_class = PropertyImageSerializer
    filterset_fields = ("property_obj", "is_cover")
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = (IsAuthenticatedOrReadOnly, IsPropertyOwnerOrReadOnly)


class PropertyRuleViewSet(viewsets.ModelViewSet):
    queryset = PropertyRule.objects.select_related("property_obj", "amenity")
    serializer_class = PropertyRuleSerializer
    filterset_fields = ("property_obj", "rule_key")
    permission_classes = (
        IsAdminOrReadOnly,
    )  # Temporary (until the 'owners' section is ready)


class PermissionRuleViewSet(viewsets.ModelViewSet):
    queryset = PermissionRule.objects.select_related("rule")
    serializer_class = PermissionRuleSerializer
    filterset_fields = ("rule", "allowed")
    permission_classes = (
        IsAdminOrReadOnly,
    )  # Temporary (until the 'owners' section is ready)


class TimeRuleViewSet(viewsets.ModelViewSet):
    queryset = TimeRule.objects.select_related("rule")
    serializer_class = TimeRuleSerializer
    filterset_fields = ("rule",)
    permission_classes = (
        IsAdminOrReadOnly,
    )  # Temporary (until the 'owners' section is ready)


class QuantityRuleViewSet(viewsets.ModelViewSet):
    queryset = QuantityRule.objects.select_related("rule")
    serializer_class = QuantityRuleSerializer
    filterset_fields = (
        "rule",
        "value",
    )
    permission_classes = (
        IsAdminOrReadOnly,
    )  # Temporary (until the 'owners' section is ready)
