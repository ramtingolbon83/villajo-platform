from rest_framework.routers import DefaultRouter

from .views import (
    AmenityViewSet,
    CategoryViewSet,
    CityViewSet,
    CountryViewSet,
    CountyViewSet,
    DistrictViewSet,
    PropertyImageViewSet,
    PropertyLocationViewSet,
    ProvinceViewSet,
    RuralDistrictViewSet,
)

router = DefaultRouter()
router.register("countries", CountryViewSet, basename="country")
router.register("provinces", ProvinceViewSet, basename="province")
router.register("counties", CountyViewSet, basename="county")
router.register("amenities", AmenityViewSet, basename="amenity")
router.register(
    "property-locations", PropertyLocationViewSet, basename="property-location"
)
router.register("property-images", PropertyImageViewSet, basename="property-image")
router.register("categories", CategoryViewSet, basename="category")
router.register("districts", DistrictViewSet, basename="district")
router.register("rural-districts", RuralDistrictViewSet, basename="rural-district")
router.register("cities", CityViewSet, basename="city")

urlpatterns = router.urls
