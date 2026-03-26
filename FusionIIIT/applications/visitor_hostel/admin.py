from django.contrib import admin

from .models import (
    Bill,
    BookingDetail,
    Building,
    GuestFeedback,
    Inventory,
    InventoryReplenishmentRequest,
    InventoryUsage,
    MealBooking,
    Notification,
    Payment,
    RoomAllocation,
    RoomDetail,
    VisitorDetail,
)


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location", "total_rooms", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(RoomDetail)
class RoomDetailAdmin(admin.ModelAdmin):
    list_display = ("room_number", "building", "room_type", "floor", "status", "tariff_per_day")
    list_filter = ("building", "room_type", "status", "floor", "has_ac")
    search_fields = ("room_number", "building__name")


@admin.register(BookingDetail)
class BookingDetailAdmin(admin.ModelAdmin):
    list_display = (
        "booking_number", "visitor_name", "visitor_category",
        "check_in_date", "check_out_date", "status", "intender",
    )
    list_filter = ("status", "visitor_category", "is_offline", "purpose")
    search_fields = ("booking_number", "visitor_name", "visitor_phone", "visitor_email")
    date_hierarchy = "check_in_date"
    readonly_fields = ("booking_number", "booking_date", "updated_at")


@admin.register(RoomAllocation)
class RoomAllocationAdmin(admin.ModelAdmin):
    list_display = ("booking", "room", "check_in_date", "check_out_date", "allocated_at")
    list_filter = ("room__building",)
    search_fields = ("booking__booking_number", "room__room_number")


@admin.register(VisitorDetail)
class VisitorDetailAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "booking", "relationship_to_intender")
    search_fields = ("full_name", "phone", "booking__booking_number")


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "booking", "total_amount", "amount_paid",
        "balance_due", "status", "invoice_date",
    )
    list_filter = ("status", "payment_mode")
    search_fields = ("invoice_number", "booking__booking_number", "billed_to_name")
    readonly_fields = ("invoice_number", "created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("bill", "amount", "payment_mode", "payment_date", "received_by")
    list_filter = ("payment_mode",)
    search_fields = ("bill__invoice_number", "reference_number")


@admin.register(MealBooking)
class MealBookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking", "meal_date", "meal_type", "number_of_persons",
        "vegetarian", "rate_per_person", "total_amount",
    )
    list_filter = ("meal_type", "vegetarian")
    search_fields = ("booking__booking_number",)
    date_hierarchy = "meal_date"


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "quantity", "usable_quantity", "unit",
        "threshold_quantity", "unit_cost", "last_updated",
    )
    list_filter = ("category",)
    search_fields = ("name", "purchase_bill_number")


@admin.register(InventoryUsage)
class InventoryUsageAdmin(admin.ModelAdmin):
    list_display = ("inventory_item", "booking", "quantity_used", "recorded_at", "recorded_by")
    search_fields = ("booking__booking_number", "inventory_item__name")
    date_hierarchy = "recorded_at"


@admin.register(InventoryReplenishmentRequest)
class InventoryReplenishmentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "quantity_requested",
        "status",
        "requested_by",
        "reviewed_by",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("inventory_item__name", "requested_by__user__username")
    date_hierarchy = "created_at"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "booking", "subject", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("recipient__username", "subject", "booking__booking_number")


@admin.register(GuestFeedback)
class GuestFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "booking", "overall_experience", "room_cleanliness",
        "staff_behavior", "submitted_at",
    )
    search_fields = ("booking__booking_number",)
