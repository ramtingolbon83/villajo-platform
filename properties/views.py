from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

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
from properties.permission import IsAdminOrReadOnly, IsPropertyOwnerOrReadOnly
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


@api_view(["GET"])
def property_list(request):
    if request.method == "GET":
        properties = Property.objects.all()
        serializer = PropertyListSerializer(properties, many=True)
        return Response(serializer.data)


@api_view(["POST"])
def property_create(request):
    if request.method == "POST":
        serializer = PropertyCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
def property_detail(request, pk):
    try:
        properties = Property.objects.get(pk=pk)
    except Property.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = PropertyDetailSerializer(properties)
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = PropertyUpdateSerializer(properties, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "PATCH":
        serializer = PropertyUpdateSerializer(
            properties, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        properties.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.prefetch_related("amenities")
    permission_classes = (IsAdminOrReadOnly,)  # موقت تا آماده شدن owner

    def get_serializer_class(self):
        return {
            "list": PropertyListSerializer,
            "retrieve": PropertyDetailSerializer,
            "create": PropertyCreateSerializer,
        }.get(self.action, PropertyUpdateSerializer)


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
