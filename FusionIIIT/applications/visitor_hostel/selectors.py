"""
Visitor Hostel Management System (VHMS) - Selectors (DB Queries)
All .objects usage lives here.
"""

from datetime import date

from django.db.models import Q, Sum

from .models import (
    Bill,
    BookingDetail,
    BookingStatus,
    Inventory,
    MealBooking,
    Notification,
    RoomAllocation,
    RoomDetail,
    RoomStatus,
)


# ──────────────────────────── Bookings ────────────────────────────

def get_booking_by_id(booking_id: int) -> BookingDetail:
    return BookingDetail.objects.select_related(
        "intender__user", "intender_department",
        "approved_by__user", "forwarded_by__user", "caretaker__user",
    ).get(pk=booking_id)


def get_booking_by_number(booking_number: str) -> BookingDetail:
    return BookingDetail.objects.select_related(
        "intender__user", "intender_department"
    ).get(booking_number=booking_number)


def get_bookings_by_intender(extrainfo_id: int):
    """VH-UC-001, VH-UC-002: Bookings by a specific intender."""
    return BookingDetail.objects.filter(intender_id=extrainfo_id).order_by("-booking_date")


def get_pending_bookings():
    """VH-UC-002 / UC-018: All pending bookings for caretaker review."""
    return BookingDetail.objects.filter(
        status=BookingStatus.PENDING
    ).select_related("intender__user").order_by("check_in_date")


def get_forwarded_bookings():
    """All forwarded bookings awaiting VH Incharge decision."""
    return BookingDetail.objects.filter(
        status=BookingStatus.FORWARDED
    ).select_related("intender__user", "forwarded_by__user").order_by("check_in_date")


def get_all_bookings(status: str = None):
    qs = BookingDetail.objects.select_related(
        "intender__user", "approved_by__user", "caretaker__user"
    ).order_by("-booking_date")
    if status:
        qs = qs.filter(status=status)
    return qs


def get_checked_in_bookings():
    """VH-UC-007 / WF-VH-002: Currently checked-in bookings."""
    return BookingDetail.objects.filter(status=BookingStatus.CHECKED_IN).order_by(
        "check_out_date"
    )


def get_bookings_for_report(start_date: date, end_date: date, status: str = None):
    """VH-UC-021: Booking report query."""
    qs = BookingDetail.objects.filter(
        booking_date__date__range=(start_date, end_date)
    ).select_related("intender__user", "intender_department")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("booking_date")


# ──────────────────────────── Rooms ────────────────────────────

def get_all_rooms(room_type: str = None, building_id: int = None):
    qs = RoomDetail.objects.select_related("building").order_by("building", "room_number")
    if room_type:
        qs = qs.filter(room_type=room_type)
    if building_id:
        qs = qs.filter(building_id=building_id)
    return qs


def get_available_rooms(
    check_in: date,
    check_out: date,
    room_type: str = None,
    building_id: int = None,
):
    """
    VH-UC-006 / VH-BR-012: Check room availability for date range.
    Excludes rooms with confirmed/checked-in overlapping allocations.
    """
    qs = RoomDetail.objects.filter(status=RoomStatus.AVAILABLE)

    if room_type:
        qs = qs.filter(room_type=room_type)
    if building_id:
        qs = qs.filter(building_id=building_id)

    conflicting_room_ids = RoomAllocation.objects.filter(
        Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in),
        booking__status__in=[BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN],
    ).values_list("room_id", flat=True)

    return qs.exclude(id__in=conflicting_room_ids).select_related("building")


def get_room_by_id(room_id: int) -> RoomDetail:
    return RoomDetail.objects.select_related("building").get(pk=room_id)


def get_conflicting_allocations(room_ids: list, check_in: date, check_out: date):
    """VH-BR-012: Detect overlapping room allocations."""
    return RoomAllocation.objects.filter(
        room_id__in=room_ids,
        booking__status__in=[BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN],
    ).filter(
        Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in)
    )


# ──────────────────────────── Bills ────────────────────────────

def get_bill_by_booking(booking_id: int) -> Bill:
    return Bill.objects.select_related("booking", "generated_by__user").get(
        booking_id=booking_id
    )


def get_bill_by_id(bill_id: int) -> Bill:
    return Bill.objects.select_related("booking", "generated_by__user").get(pk=bill_id)


def get_all_bills(status: str = None):
    """VH-UC-014: View bills and payment status."""
    qs = Bill.objects.select_related("booking__intender__user").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    return qs


# ──────────────────────────── Meals ────────────────────────────

def get_meals_for_booking(booking_id: int):
    """VH-UC-009: Meals for a specific booking."""
    return MealBooking.objects.filter(booking_id=booking_id).order_by("meal_date", "meal_type")


# ──────────────────────────── Inventory ────────────────────────────

def get_all_inventory(category: str = None):
    """VH-UC-012: View inventory stock."""
    qs = Inventory.objects.order_by("name")
    if category:
        qs = qs.filter(category=category)
    return qs


def get_inventory_by_id(item_id: int) -> Inventory:
    return Inventory.objects.get(pk=item_id)


def get_low_stock_items():
    """BR-VH-007: Items below threshold."""
    from django.db.models import F
    return Inventory.objects.filter(quantity__lt=F("threshold_quantity"))


# ──────────────────────────── Notifications ────────────────────────────

def get_unread_notifications(user_id: int):
    return Notification.objects.filter(recipient_id=user_id, is_read=False).order_by(
        "-created_at"
    )


def get_all_notifications(user_id: int):
    return Notification.objects.filter(recipient_id=user_id).order_by("-created_at")


# ──────────────────────────── Dashboard ────────────────────────────

def get_dashboard_stats():
    """VH-UC-016: Dashboard overview statistics."""
    return {
        "total_bookings": BookingDetail.objects.count(),
        "pending_bookings": BookingDetail.objects.filter(status=BookingStatus.PENDING).count(),
        "confirmed_bookings": BookingDetail.objects.filter(status=BookingStatus.CONFIRMED).count(),
        "checked_in": BookingDetail.objects.filter(status=BookingStatus.CHECKED_IN).count(),
        "checked_out_today": BookingDetail.objects.filter(
            status=BookingStatus.CHECKED_OUT,
            actual_check_out__date=date.today(),
        ).count(),
        "available_rooms": RoomDetail.objects.filter(status=RoomStatus.AVAILABLE).count(),
        "occupied_rooms": RoomDetail.objects.filter(status=RoomStatus.OCCUPIED).count(),
        "low_stock_items": get_low_stock_items().count(),
        "pending_bills": Bill.objects.filter(status__in=["Generated", "Pending"]).count(),
    }
