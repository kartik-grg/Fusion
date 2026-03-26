"""
Visitor Hostel Management System (VHMS) - Serializers
DRF serializers with field-level validation.
"""

from datetime import date
from decimal import Decimal

from rest_framework import serializers

from ..models import (
    Bill,
    BookingDetail,
    BookingStatus,
    Building,
    GuestFeedback,
    Inventory,
    InventoryReplenishmentRequest,
    InventoryCategory,
    MealBooking,
    Notification,
    Payment,
    RoomAllocation,
    RoomDetail,
    RoomFloor,
    RoomStatus,
    RoomType,
    VisitorCategory,
    VisitorDetail,
)


# ──────────────────────────── Room Serializers ────────────────────────────

class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = "__all__"


class RoomDetailSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source="building.name", read_only=True)
    building_code = serializers.CharField(source="building.code", read_only=True)

    class Meta:
        model = RoomDetail
        fields = [
            "id", "building", "building_name", "building_code",
            "room_number", "room_type", "floor", "bed_count", "max_occupancy",
            "has_ac", "has_attached_bathroom", "amenities", "status",
            "tariff_per_day", "tariff_faculty", "tariff_staff",
            "tariff_student", "tariff_external",
        ]
        read_only_fields = ["id"]

    def validate_floor(self, value):
        """VH-BR-032"""
        valid = [c[0] for c in RoomFloor.choices]
        if value not in valid:
            raise serializers.ValidationError(f"Floor must be one of: {valid}")
        return value

    def validate_room_type(self, value):
        """VH-BR-031"""
        valid = [c[0] for c in RoomType.choices]
        if value not in valid:
            raise serializers.ValidationError(f"Room type must be one of: {valid}")
        return value

    def validate_tariff_per_day(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Tariff cannot be negative.")
        return value


class RoomAvailabilitySerializer(serializers.Serializer):
    """VH-UC-006: Check room availability."""
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    room_type = serializers.ChoiceField(choices=RoomType.choices, required=False, allow_blank=True)
    building_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        """VH-BR-023 / VH-BR-041"""
        ci = attrs.get("check_in_date")
        co = attrs.get("check_out_date")
        if ci and co:
            if ci >= co:
                raise serializers.ValidationError("Check-out must be after check-in.")
            if ci < date.today():
                raise serializers.ValidationError("Check-in cannot be in the past.")
        return attrs


# ──────────────────────────── Booking Serializers ────────────────────────────

class VisitorDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitorDetail
        fields = [
            "id", "full_name", "phone", "email",
            "id_proof_type", "id_proof_number", "relationship_to_intender",
        ]

    def validate(self, attrs):
        """VH-BR-025: Minimum visitor details"""
        if not attrs.get("full_name") or not attrs.get("phone"):
            raise serializers.ValidationError("Full name and phone are required.")
        return attrs


class BookingCreateSerializer(serializers.ModelSerializer):
    """Used for VH-UC-001: request_booking"""

    class Meta:
        model = BookingDetail
        fields = [
            "visitor_name", "visitor_category", "visitor_phone", "visitor_email",
            "visitor_organization", "visitor_designation", "visitor_address",
            "id_proof_type", "id_proof_number",
            "check_in_date", "check_out_date",
            "number_of_guests", "number_of_rooms", "preferred_room_type",
            "purpose", "purpose_details",
            "bill_to_be_settled_by", "project_number", "remark",
            "is_offline",
        ]

    def validate_visitor_category(self, value):
        """VH-BR-030"""
        valid = [c[0] for c in VisitorCategory.choices]
        if value not in valid:
            raise serializers.ValidationError(f"Invalid visitor category. Must be one of: {valid}")
        return value

    def validate_number_of_guests(self, value):
        """VH-BR-024"""
        if value < 1:
            raise serializers.ValidationError("Number of guests must be at least 1.")
        return value

    def validate_number_of_rooms(self, value):
        """VH-BR-024"""
        if value < 1:
            raise serializers.ValidationError("Number of rooms must be at least 1.")
        return value

    def validate_remark(self, value):
        """VH-BR-034"""
        if len(value) > 500:
            raise serializers.ValidationError("Remark cannot exceed 500 characters.")
        return value

    def validate(self, attrs):
        """VH-BR-023 / VH-BR-041"""
        ci = attrs.get("check_in_date")
        co = attrs.get("check_out_date")
        if ci and co:
            if ci >= co:
                raise serializers.ValidationError("Check-out date must be after check-in date.")
            if ci < date.today():
                raise serializers.ValidationError("Check-in date cannot be in the past.")
        if not attrs.get("visitor_name") or not attrs.get("visitor_phone"):
            raise serializers.ValidationError("Visitor name and phone are required.")  # VH-BR-025
        return attrs


class BookingModifySerializer(serializers.ModelSerializer):
    """UC-VH-017 / VH-UC-003: Modify Booking Request"""

    class Meta:
        model = BookingDetail
        fields = [
            "visitor_name", "visitor_category", "visitor_phone", "visitor_email",
            "visitor_organization", "visitor_designation", "visitor_address",
            "id_proof_type", "id_proof_number",
            "check_in_date", "check_out_date",
            "number_of_guests", "number_of_rooms", "preferred_room_type",
            "purpose", "purpose_details",
            "bill_to_be_settled_by", "project_number", "remark",
        ]

    def validate(self, attrs):
        ci = attrs.get("check_in_date")
        co = attrs.get("check_out_date")
        if ci and co and ci >= co:
            raise serializers.ValidationError("Check-out must be after check-in.")
        return attrs


class BookingListSerializer(serializers.ModelSerializer):
    intender_name = serializers.CharField(source="intender.user.get_full_name", read_only=True)
    intender_email = serializers.CharField(source="intender.user.email", read_only=True)
    department = serializers.CharField(source="intender_department.name", read_only=True, default="")

    class Meta:
        model = BookingDetail
        fields = [
            "id", "booking_number", "intender_name", "intender_email", "department",
            "visitor_name", "visitor_category", "visitor_phone", "visitor_email",
            "check_in_date", "check_out_date", "number_of_guests", "number_of_rooms",
            "purpose", "status", "booking_date", "is_offline",
            "cancellation_charge", "cancellation_requested_at",
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    intender_name = serializers.CharField(source="intender.user.get_full_name", read_only=True)
    intender_email = serializers.CharField(source="intender.user.email", read_only=True)
    department = serializers.CharField(source="intender_department.name", read_only=True, default="")
    approved_by_name = serializers.CharField(source="approved_by.user.get_full_name", read_only=True, default="")
    forwarded_by_name = serializers.CharField(source="forwarded_by.user.get_full_name", read_only=True, default="")
    room_allocations = serializers.SerializerMethodField()
    visitor_details = VisitorDetailSerializer(many=True, read_only=True)

    class Meta:
        model = BookingDetail
        fields = "__all__"

    def get_room_allocations(self, obj):
        allocs = obj.room_allocations.select_related("room__building").all()
        return [
            {
                "id": a.id,
                "room_number": a.room.room_number,
                "building": a.room.building.name,
                "room_type": a.room.room_type,
            }
            for a in allocs
        ]


class ForwardBookingSerializer(serializers.Serializer):
    """VH-UC-003: Forward booking to VH Incharge"""
    booking_id = serializers.IntegerField()


class ConfirmBookingSerializer(serializers.Serializer):
    """VH-UC-004: Confirm booking with room assignment — VH-BR-022"""
    booking_id = serializers.IntegerField()
    room_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class RejectBookingSerializer(serializers.Serializer):
    """VH-UC-004: Reject booking"""
    booking_id = serializers.IntegerField()
    reason = serializers.CharField()


class CancelBookingSerializer(serializers.Serializer):
    """VH-UC-005 / VH-UC-019 / VH-UC-020"""
    booking_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class CancellationPreviewSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()


class ApproveCancellationSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()


class CheckInSerializer(serializers.Serializer):
    """VH-UC-007: Check in visitors — VH-BR-017"""
    booking_id = serializers.IntegerField()
    visitor_details = VisitorDetailSerializer(many=True, required=False, default=list)


class NoShowSerializer(serializers.Serializer):
    """VH-UC-007 Alternate Flow A1: Mark booking as no-show."""
    booking_id = serializers.IntegerField()


class CheckOutSerializer(serializers.Serializer):
    """VH-UC-008: Check-out and billing with overstay handling"""
    booking_id = serializers.IntegerField()
    extra_charges = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    overstay_hours = serializers.IntegerField(default=0, min_value=0)
    overstay_charges = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    inventory_usage = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )

    def validate_extra_charges(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Extra charges cannot be negative.")
        return value

    def validate_overstay_hours(self, value):
        """Validate overstay hours"""
        if value < 0:
            raise serializers.ValidationError("Overstay hours cannot be negative.")
        return value

    def validate_overstay_charges(self, value):
        """Validate overstay charges"""
        if value < 0:
            raise serializers.ValidationError("Overstay charges cannot be negative.")
        return value

    def validate_discount(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return value


# ──────────────────────────── Bill Serializers ────────────────────────────

class BillSerializer(serializers.ModelSerializer):
    """VH-UC-013 / VH-UC-014: Bills"""
    booking_number = serializers.CharField(source="booking.booking_number", read_only=True)
    visitor_name = serializers.CharField(source="booking.visitor_name", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.user.get_full_name", read_only=True, default="")

    class Meta:
        model = Bill
        fields = "__all__"
        read_only_fields = [
            "id", "invoice_number", "created_at", "updated_at",
            "booking_number", "visitor_name", "generated_by_name",
        ]


class SettleBillSerializer(serializers.Serializer):
    """VH-UC-015: Settle bill"""
    bill_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = serializers.ChoiceField(choices=Payment._meta.get_field("payment_mode").choices)
    reference_number = serializers.CharField(required=False, allow_blank=True, default="")
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_amount(self, value):
        """VH-BR-024"""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


# ──────────────────────────── Meal Serializers ────────────────────────────

class MealBookingSerializer(serializers.ModelSerializer):
    """VH-UC-009: Record meal"""
    booking_number = serializers.CharField(source="booking.booking_number", read_only=True)

    class Meta:
        model = MealBooking
        fields = [
            "id", "booking", "booking_number", "meal_date", "meal_type",
            "number_of_persons", "vegetarian", "special_requirements",
            "rate_per_person", "total_amount", "created_at",
        ]
        read_only_fields = ["id", "total_amount", "booking_number", "created_at"]

    def validate_number_of_persons(self, value):
        """VH-BR-024"""
        if value < 1:
            raise serializers.ValidationError("Number of persons must be at least 1.")
        return value

    def validate_rate_per_person(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Rate cannot be negative.")
        return value


# ──────────────────────────── Inventory Serializers ────────────────────────────

class InventorySerializer(serializers.ModelSerializer):
    """VH-UC-010 / VH-UC-011 / VH-UC-012"""
    added_by_name = serializers.CharField(source="added_by.user.get_full_name", read_only=True, default="")

    class Meta:
        model = Inventory
        fields = [
            "id", "name", "category", "description", "quantity",
            "usable_quantity", "unit", "purchase_bill_number",
            "purchase_date", "unit_cost", "threshold_quantity",
            "added_by", "added_by_name", "last_updated", "created_at",
        ]
        read_only_fields = ["id", "last_updated", "created_at", "added_by_name"]

    def validate_quantity(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    def validate_unit_cost(self, value):
        """VH-BR-024"""
        if value < 0:
            raise serializers.ValidationError("Unit cost cannot be negative.")
        return value


class InventoryUpdateSerializer(serializers.Serializer):
    """VH-UC-011: Update inventory quantities"""
    item_id = serializers.IntegerField()
    quantity_delta = serializers.IntegerField(
        help_text="Positive to add, negative to reduce."
    )


class InventoryReplenishmentRequestSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.user.get_full_name", read_only=True, default="")
    reviewed_by_name = serializers.CharField(source="reviewed_by.user.get_full_name", read_only=True, default="")

    class Meta:
        model = InventoryReplenishmentRequest
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "requested_by",
            "requested_by_name",
            "quantity_requested",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_remark",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requested_by",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
            "inventory_item_name",
            "requested_by_name",
            "reviewed_by_name",
        ]


class InventoryReplenishmentCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity_requested = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class InventoryReplenishmentReviewSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    approve = serializers.BooleanField()
    review_remark = serializers.CharField(required=False, allow_blank=True, default="")


# ──────────────────────────── Notification / Feedback ────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "subject", "message", "is_read", "created_at"]
        read_only_fields = ["id", "subject", "message", "created_at"]


class GuestFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestFeedback
        fields = [
            "id", "booking",
            "room_cleanliness", "room_amenities", "staff_behavior",
            "food_quality", "overall_experience",
            "comments", "suggestions", "submitted_at",
        ]
        read_only_fields = ["id", "submitted_at"]
