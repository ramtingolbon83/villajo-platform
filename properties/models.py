from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils.text import slugify

ACCOMMODATION = "اقامتگاه"
REGULATION = "قانون"

# ==================================================
#                  Abstract Base Model
# ==================================================
"""An abstract model that adds a unique, automatic slug field to any model inheriting from it."""


class SluggedModel(models.Model):
    slug = models.SlugField(
        unique=True, allow_unicode=True, blank=True, verbose_name="اسلاگ"
    )

    class Meta:
        abstract = True

    def auto_filler(self):
        source = getattr(self, "name", None) or getattr(self, "title", None)
        if not source:
            return None
        base_slug = slugify(source, allow_unicode=True)
        slug = base_slug
        counter = 1
        while self.__class__.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.auto_filler()

        max_attempts = 5

        for attempts in range(max_attempts):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if attempts == max_attempts - 1:
                    raise
                self.slug = self.auto_filler()


# ==================================================
#              Shared Choice Definitions
# ==================================================
"""Possible statuses for the approval of a property by an inspector."""


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "تاییدنشده"
    PENDING = "pending", "در انتظار بررسی"
    VERIFIED = "verified", "تاییدشده"
    REJECTED = "rejected", "ردشده"


"""Types of general rules definable for a property."""


class GeneralRule(models.TextChoices):
    PARTY = "party", "مهمانی"
    SMOKING = "smoking", "سیگار"
    PETS = "pets", "حیوانات خانگی"
    QUIET_HOURS = "quiet_hours", "ساعات سکوت"
    CHECK_IN = "check_in", "ورود"
    CHECK_OUT = "check_out", "خروج"
    EXTRA_GUESTS = "extra_guests", "مهمان اضافه"
    VISITORS = "visitors", "مراجعه‌کننده"
    AGE_RESTRICTION = "age_restriction", "محدودیت سنی"
    FILMING = "filming", "فیلم‌برداری و عکاسی"
    EVENT = "event", "برگزاری مراسم"


# ==================================================
#     Key Accommodation Information
# ==================================================
class Property(SluggedModel):
    PROPERTY_TYPE_CHOICES = (
        ("villa", "ویلا"),
        ("cottage", "کلبه"),
        ("apartment", "آپارتمان"),
        ("suite", "سوئیت"),
        ("house", "خانه"),
        ("eco_lodge", "بوم‌گردی"),
    )
    amenities = models.ManyToManyField(
        "Amenity", related_name="properties", blank=True, verbose_name="امکانات رفاهی"
    )
    # Identity
    title = models.CharField(max_length=150, verbose_name="عنوان")

    description = models.TextField(verbose_name="توضیحات")
    property_type = models.CharField(
        max_length=20, choices=PROPERTY_TYPE_CHOICES, verbose_name="نوع ملک"
    )

    # Capacity & Physical Information
    max_guests = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], verbose_name="تعداد مهمان"
    )
    bedrooms = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], verbose_name="تعداد اتاق "
    )
    beds = models.PositiveIntegerField(verbose_name="تعداد تخت")
    bathrooms = models.PositiveIntegerField(default=1, verbose_name="تعداد حمام")
    toilets = models.PositiveIntegerField(
        default=1, verbose_name="تعداد سرویس بهداشتی "
    )
    building_area = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="مساحت ساختمان"
    )
    land_area = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="مساحت زمین"
    )
    floor = models.IntegerField(default=1, verbose_name="طبقه")

    # Ownership
    # owner =

    # Status
    STATUS_CHOICES = (
        ("draft", "پیش نویس"),
        ("pending_review", "در انتظار برسی"),
        ("published", "منتشر شده"),
        ("rejected", "رد شده"),
        ("paused", "متوقف شده"),
        ("suspended", "تعلیق شده"),
        ("archived", "بایگانی شده"),
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="وضعیت اقامتگاه",
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        verbose_name="وضعیت تایید بازرس",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="تاریخ آخرین بروزرسانی"
    )
    published_at = models.DateTimeField(
        null=True, blank=True, verbose_name="تاریخ انتشار "
    )

    class Meta:
        verbose_name = "ملک"
        verbose_name_plural = "املاک"

    def __str__(self):
        return self.title


# ===================================================
#                   Location
# ===================================================
class Country(SluggedModel):
    # Identity
    name = models.CharField(max_length=60, verbose_name="نام کشور", unique=True)
    code = models.CharField(max_length=6, verbose_name="کد کشور", unique=True)

    class Meta:
        verbose_name = "کشور"
        verbose_name_plural = "کشور ها"

    def __str__(self):
        return self.name


class Province(SluggedModel):
    # Relationship
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="provinces", verbose_name="کشور"
    )
    # Identity
    name = models.CharField(max_length=200, verbose_name="نام استان")
    code = models.CharField(max_length=6, verbose_name="کد استان")

    class Meta:
        verbose_name = "استان/ایالت"
        verbose_name_plural = "استان ها / ایالت ها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["country", "code"],
                name="unique_province_code_per_country",
            )
        ]

    def __str__(self):
        return self.name


class County(SluggedModel):
    # Relationship
    province = models.ForeignKey(
        Province,
        on_delete=models.CASCADE,
        related_name="counties",
        verbose_name="استان",
    )
    # Identity
    name = models.CharField(max_length=200, verbose_name="نام شهرستان")
    code = models.CharField(max_length=6, verbose_name="کد شهرستان")

    class Meta:
        verbose_name = "شهرستان/ناحیه"
        verbose_name_plural = "شهرستان ها/ناحیه ها"
        constraints = (
            models.UniqueConstraint(
                fields=["province", "code"],
                name="unique_county_code_per_province",
            ),
        )

    def __str__(self):
        return self.name


class District(SluggedModel):
    # Relationship
    county = models.ForeignKey(
        County,
        on_delete=models.CASCADE,
        related_name="districts",
        verbose_name="شهرستان",
    )
    # Identity
    name = models.CharField(max_length=200, verbose_name="نام بخش")
    code = models.CharField(max_length=6, verbose_name="کد بخش")

    class Meta:
        verbose_name = "بخش"
        verbose_name_plural = "بخش ها"

    def __str__(self):
        return self.name


class RuralDistrict(SluggedModel):
    # Relationship
    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="rural_districts",
        verbose_name="بخش",
    )
    # Identity
    name = models.CharField(max_length=200, verbose_name="نام دهستان")
    code = models.CharField(max_length=6, verbose_name="کد دهستان")

    class Meta:
        verbose_name = "دهستان/روستا"
        verbose_name_plural = "دهستان ها/روستا ها"

    def __str__(self):
        return self.name


class City(SluggedModel):
    # Relationship
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="cities", verbose_name="استان"
    )
    county = models.ForeignKey(
        County, on_delete=models.CASCADE, related_name="cities", verbose_name="شهرستان"
    )
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="cities", verbose_name="بخش"
    )
    # Identity
    name = models.CharField(max_length=200, verbose_name="نام شهر")
    code = models.CharField(max_length=6, verbose_name="کد شهر")

    class Meta:
        verbose_name = "شهر"
        verbose_name_plural = "شهر ها"

    def __str__(self):
        return self.name


class PropertyLocation(models.Model):
    # Relationship
    property_obj = models.OneToOneField(
        Property,
        on_delete=models.CASCADE,
        related_name="location",
        verbose_name="موقعیت مکانی",
    )

    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name="properties", verbose_name="شهر"
    )
    # Address
    address = models.CharField(
        max_length=350, blank=True, verbose_name="آدرس تکمیلی"
    )
    postal_code = models.CharField(max_length=10, verbose_name="کد پستی")

    # Geographic Coordinates
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name="عرض جغرافیایی"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name="طول جغرافیایی"
    )


# ==================================================
#                       Amenity
# ==================================================
class Category(SluggedModel):
    name = models.CharField(max_length=200, verbose_name="نام طبقه بندی")
    is_active = models.BooleanField(default=False, verbose_name="وضعیت")

    class Meta:
        verbose_name = "دسته بندی"
        verbose_name_plural = "مدیریت دسته بندی ها"

    def __str__(self):
        return self.name


class Amenity(SluggedModel):
    # Relationship
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="amenities",
        verbose_name="طبقه بندی ",
    )

    # Identity
    name = models.CharField(max_length=50, verbose_name="نام امکانات رفاهی")

    # Status
    is_active = models.BooleanField(default=False, verbose_name="وضعیت")

    class Meta:
        verbose_name = "امکانات رفاهی"
        verbose_name_plural = "مدیریت امکانات رفاهی"

    def __str__(self):
        return self.name


# ==================================================
#                       Images
# ==================================================
class PropertyImage(models.Model):
    # Relationship
    property_obj = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=ACCOMMODATION,
    )

    # Image
    image = models.ImageField(upload_to="properties/images/", verbose_name="تصویر")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="متن جایگزین")

    # Display
    is_cover = models.BooleanField(default=False, verbose_name="تصویر اصلی")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="تاریخ اخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "تصویر ملک"
        verbose_name_plural = "تصاویر ملک‌ها"
        ordering = ("order", "id")
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["property_obj"],
                condition=models.Q(is_cover=True),
                name="unique_cover_per_property",
            )
        ]

    def __str__(self):
        return f"{self.property_obj} - {self.order}"


# ===================================================
#                Laws and regulations
# ===================================================
class PropertyRule(models.Model):
    # Relations
    property_obj = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="rules", verbose_name="ملک"
    )
    amenity = models.ForeignKey(
        Amenity,
        on_delete=models.CASCADE,
        related_name="rules",
        null=True,
        blank=True,
        verbose_name="امکانات",
    )

    # Classification
    rule_key = models.CharField(
        max_length=50,
        choices=GeneralRule.choices,
        verbose_name="نوع قانون",
    )


class PermissionRule(models.Model):
    # Relation
    rule = models.OneToOneField(
        PropertyRule,
        on_delete=models.CASCADE,
        related_name="permission",
        verbose_name=REGULATION,
    )

    # Value
    allowed = models.BooleanField(default=False, verbose_name="مجوز")


class TimeRule(models.Model):
    # Relation
    rule = models.OneToOneField(
        PropertyRule,
        on_delete=models.CASCADE,
        related_name="time",
        verbose_name=REGULATION,
    )

    # Time
    start_time = models.TimeField()
    end_time = models.TimeField()


class QuantityRule(models.Model):
    # Relation
    rule = models.OneToOneField(
        PropertyRule,
        on_delete=models.CASCADE,
        related_name="quantity",
        verbose_name=REGULATION,
    )

    # Value
    value = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="تعداد مجاز"
    )


# ===================================================
#               Cancellation Policies
# ===================================================
class CancellationPolicy(SluggedModel):
    # Relations
    property_obj = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="cancellation_policies",
        verbose_name=ACCOMMODATION,
    )

    # Identity & Basic Information
    title = models.CharField(max_length=350, verbose_name="عنوان سیاست")
    description = models.TextField(verbose_name="توضیحات تکمیلی")

    # Status & Timestamps
    is_active = models.BooleanField(default=False, verbose_name="وضعیت فعالیت")

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="تاریخ و زمان ثبت"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="تاریخ و زمان آخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "سیاست لغو"
        verbose_name_plural = "قوانین لغو رزرو"

    def __str__(self):
        return self.title


class CancellationRule(models.Model):
    # Relation
    policy = models.ForeignKey(
        CancellationPolicy,
        on_delete=models.CASCADE,
        related_name="rules",
        verbose_name="سیاست لغو",
    )

    # Conditions
    hours_before_checkin = models.PositiveIntegerField(
        verbose_name="تعداد ساعت های باقی مانده"
    )
    hours_before_checkin_max = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="حداکثر ساعت باقی مانده "
    )
    # Values
    refund_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="درصد بازگشت وجه"
    )

    # Additional Rules
    charge_first_night = models.BooleanField(
        default=False, verbose_name="کسر هزینه شب اول"
    )

    # Display & Ordering
    note = models.CharField(
        max_length=1000, verbose_name="توضیحات کوتاه برای نمایش در فاکتور"
    )

    priority = models.PositiveIntegerField(verbose_name="ترتیب برسی قانون")


# ====================================================
#         Accommodation Verification Status
# ====================================================
class PropertyVerification(models.Model):
    # Relation
    property_obj = models.OneToOneField(
        Property,
        on_delete=models.CASCADE,
        related_name="verification",
        verbose_name=ACCOMMODATION,
    )

    # Verification Status
    status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, verbose_name="وضعیت تایید"
    )

    # Verification Information
    verified_at = models.DateTimeField(
        null=True, blank=True, verbose_name="تاریخ و زمان تأیید"
    )

    # verified_by = models.ForeignKey()

    # Rejection
    rejection_reason = models.TextField(
        max_length=1000, null=True, blank=True, verbose_name="دلیل رد "
    )

    # Notes
    admin_note = models.TextField(
        max_length=1000, null=True, blank=True, verbose_name="یادداشت مدیر"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="تاریخ و زمان ثبت"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="تاریخ و زمان آخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "وضعیت تایید ملک"
        verbose_name_plural = "وضعیت های تایید ملک"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.property_obj}-{self.get_status_display()}"
