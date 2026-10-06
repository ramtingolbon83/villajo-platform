# ============================================================
# Imports 
# ============================================================

from rest_framework import serializers

from .models import Booking, Payment, Villa

# ============================================================
# Villa Serializer
# ============================================================

class VillaSerializer(serializers.ModelSerializer):

    # --------------------------------------------------------
    # The Host Is Not Specified By The User Via The API. 
    # Its Value In The View Is Determined Based On The Logged-In User.
    # --------------------------------------------------------

    host = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

    # ========================================================
    # Serializer Setting
    # ========================================================

    class Meta:

        model = Villa

        # Fields Displayed In The API
        fields = (
            "id",
            "host",
            "title",
            "capacity",
            "base_price",
            "cleaning_fee",
            "service_fee",
            "extra_guest_threshold",
            "extra_guest_fee",
            "created_at",
            "updated_at",
        )

        # Read-Only Fields
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


# ============================================================
# Payment-Related Serializer
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):

    # --------------------------------------------------------
    # The Payment Status Is Determined By The Payment Gateway's Callback
    # --------------------------------------------------------

    status = serializers.ChoiceField(
        choices=Payment.Status.choices,
        read_only=True
    )

    # --------------------------------------------------------
    # The Transaction ID Is Determined By The Payment System
    # --------------------------------------------------------

    transaction_id = serializers.CharField(
        read_only=True
    )

    # --------------------------------------------------------
    # The Time Of Successful Payment Is Determined Within The System
    # --------------------------------------------------------

    paid_at = serializers.DateTimeField(
        read_only=True
    )

    # ========================================================
    # Stting Serializer
    # ========================================================

    class Meta:

        model = Payment

        fields = (
            "id",
            "booking",
            "amount",
            "status",
            "transaction_id",
            "payment_gateway",
            "paid_at",
            "created_at",
        )

        read_only_fields = (
            "id",
            "created_at",
        )

    # ========================================================
    # Payment-Related Reservation Validation
    # ========================================================

    def validate_booking(self, booking):

        request = self.context.get("request")

        if (
            request is not None
            and request.user.is_authenticated
            and booking.guest_id != request.user.id
        ):
            raise serializers.ValidationError(
                "شما اجازه‌ی ثبت پرداخت برای این رزرو را ندارید."
            )

        return booking


# ============================================================
# Reservation Serializer
# ============================================================

class BookingSerializer(serializers.ModelSerializer):

    # --------------------------------------------------------
    # The Guest User Is Not Determined By The Client. 
    # It Is Initialized In The View Based On Request.User.
    # --------------------------------------------------------

    guest = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

    # --------------------------------------------------------
    # The Reservation Creator Is Not Specified By The Client
    # --------------------------------------------------------

    created_by = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

    # --------------------------------------------------------
    # The User Who Cancelled The Reservation Is Determined By The System
    # --------------------------------------------------------

    cancelled_by = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

    # --------------------------------------------------------
    # Show Payments For This Reservation
    # --------------------------------------------------------

    payments = PaymentSerializer(
        many=True,
        read_only=True
    )

    # ========================================================
    # Setting Serializer
    # ========================================================

    class Meta:

        model = Booking

        fields = (
            "id",
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
            "payments",
            "created_at",
            "updated_at",
        )

        # ----------------------------------------------------
        # Fields That Are Not Directly Specified By The User
        # ----------------------------------------------------

        read_only_fields = (
            "id",
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
            "created_at",
            "updated_at",
        )

    # ========================================================
    # Overall Validation Of Booking Information
    # ========================================================

    def validate(self, attrs):

        instance = self.instance

        villa = attrs.get(
            "villa",
            getattr(instance, "villa", None)
        )

        check_in = attrs.get(
            "check_in",
            getattr(instance, "check_in", None)
        )

        check_out = attrs.get(
            "check_out",
            getattr(instance, "check_out", None)
        )

        guests_count = attrs.get(
            "guests_count",
            getattr(instance, "guests_count", None)
        )

        # ====================================================
        # Verifying The Accuracy Of Check-In And Check-Out Dates
        # ====================================================

        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError(
                {
                    "check_out":
                    "تاریخ خروج باید بعد از تاریخ ورود باشد."
                }
            )

        # ====================================================
        # Checking The Villa Capacity
        # ====================================================

        if villa and guests_count and guests_count > villa.capacity:
            raise serializers.ValidationError(
                {
                    "guests_count":
                    f"ظرفیت این ویلا {villa.capacity} نفر است."
                }
            )

        # ====================================================
        # Retrieve Requesting User
        # ====================================================

        request = self.context.get("request")

        # ----------------------------------------------------
        # Prevention Of The Villa Being Booked By The Host Of That Same Villa.
        # ----------------------------------------------------

        if (
            villa
            and request is not None
            and request.user.is_authenticated
        ):
            raise serializers.ValidationError(
                "میزبان نمی تواند برای ویلای خودش رزرو ثبت کند "
            )

        # ====================================================
        # Reviewing Overlapping Reservations
        # ====================================================

        if villa and check_in and check_out:

            overlapping = Booking.objects.filter(
                villa=villa,
                status__in=Booking.ACTIVE_STATUSES,
                check_in__lt=check_out,
                check_out__gt=check_in,
            )

            if instance is not None:
                overlapping = overlapping.exclude(
                    pk=instance.pk
                )

            if overlapping.exists():
                raise serializers.ValidationError(
                    "این ویلا در بازه‌ی زمانی انتخاب‌شده "
                    "قبلاً رزرو شده است."
                )

        return attrs

    # ============================================================
    # Booking Status Validation
    # ============================================================

    def validate_status(self, value):

        instance = self.instance

        # --------------------------------------------------------
        # When Creating A Reservation, The Status Must Be PENDING.
        # --------------------------------------------------------

        if instance is None:

            if value != Booking.Status.PENDING:
                raise serializers.ValidationError(
                    "وضعیت اولیه‌ی رزرو باید «در انتظار پرداخت» باشد."
                )

            return value

        # --------------------------------------------------------
        # If The New State Is The Same As The Previous State,
        # There Is No Need To Check For A State Transition.
        # --------------------------------------------------------

        if value == instance.status:
            return value

        # --------------------------------------------------------
        # Reviewing The Permissibility Of A Status Change
        # --------------------------------------------------------

        if not instance.can_transition_to(value):
            raise serializers.ValidationError(
                f"انتقال وضعیت از "
                f"«{instance.get_status_display()}» "
                "به این وضعیت مجاز نیست."
            )

        return value
