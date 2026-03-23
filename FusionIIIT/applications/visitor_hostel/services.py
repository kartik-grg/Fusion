"""
Visitor Hostel Management System (VHMS) - Services (Business Logic)
Implements all BRs from functional_requirements.xlsx
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from applications.globals.models import ExtraInfo

from .models import (
    Bill, BillStatus, BookingDetail, BookingStatus, Inventory,
    InventoryUsage, MealBooking, MealType, Notification, Payment,
    PaymentMode, RoomAllocation, RoomDetail, RoomStatus, VisitorDetail,
    VisitorCategory,
)

logger = logging.getLogger(__name__)


# ──────────────────────────── Custom Exceptions ────────────────────────────

class VHError(Exception):
    """Base exception for VHMS"""


class BookingNotFoundError(VHError):
    pass


class InvalidStatusTransitionError(VHError):
    """VH-BR-005 / VH-BR-007"""
    pass


class RoomNotAvailableError(VHError):
    """VH-BR-006 / VH-BR-012"""
    pass


class BillingLockedError(VHError):
    """VH-BR-040 / BR-VH-040"""
    pass


class ValidationError(VHError):
    pass


class PermissionDeniedError(VHError):
    pass


class MealDeadlineError(VHError):
    """BR-VH-011: Meal Booking Deadline"""
    pass


# ──────────────────────────── Helpers ────────────────────────────

# Valid status transitions — VH-BR-005
VALID_TRANSITIONS = {
    BookingStatus.PENDING: [
        BookingStatus.FORWARDED,
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ],
    BookingStatus.FORWARDED: [
        BookingStatus.CONFIRMED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.PENDING,  # returned after modification
    ],
    BookingStatus.CONFIRMED: [
        BookingStatus.CHECKED_IN,
        BookingStatus.CANCELLED,
    ],
    BookingStatus.CHECKED_IN: [
        BookingStatus.CHECKED_OUT,
    ],
    BookingStatus.CHECKED_OUT: [],     # terminal
    BookingStatus.CANCELLED: [],       # terminal
    BookingStatus.REJECTED: [],        # terminal
    BookingStatus.EXPIRED: [],         # terminal
}


def _validate_transition(current: str, next_status: str):
    """VH-BR-005, VH-BR-007: Validate booking status transition."""
    allowed = VALID_TRANSITIONS.get(current, [])
    if next_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot move booking from '{current}' to '{next_status}'."
        )


def _generate_booking_number() -> str:
    """VH-BR-033: Auto-assign booking creation timestamp / unique number."""
    today = date.today()
    prefix = f"VH{today.strftime('%Y%m%d')}"
    last = (
        BookingDetail.objects.filter(booking_number__startswith=prefix)
        .order_by("-booking_number")
        .first()
    )
    seq = int(last.booking_number[-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _generate_invoice_number() -> str:
    today = date.today()
    prefix = f"INV{today.strftime('%Y%m%d')}"
    last = (
        Bill.objects.filter(invoice_number__startswith=prefix)
        .order_by("-invoice_number")
        .first()
    )
    seq = int(last.invoice_number[-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _get_room_rate(room: RoomDetail, visitor_category: str) -> Decimal:
    """VH-BR-001: Calculate Room Bill by Visitor Category."""
    if visitor_category in [VisitorCategory.IIIT_FACULTY]:
        return room.tariff_faculty or room.tariff_per_day
    elif visitor_category in [VisitorCategory.IIIT_STAFF]:
        return room.tariff_staff or room.tariff_per_day
    elif visitor_category == VisitorCategory.IIIT_STUDENT:
        return room.tariff_student or room.tariff_per_day
    else:
        return room.tariff_external or room.tariff_per_day


def _notify(user_id: int, booking: BookingDetail, subject: str, message: str):
    """VH-BR-014: Send notification on booking status change."""
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(pk=user_id)
        Notification.objects.create(
            recipient=user,
            booking=booking,
            subject=subject,
            message=message,
        )
    except Exception as exc:
        logger.warning("Notification failed: %s", exc)


# ──────────────────────────── UC-001: Request Booking ────────────────────────────

@transaction.atomic
def create_booking(
    intender_extrainfo: ExtraInfo,
    visitor_name: str,
    visitor_category: str,
    visitor_phone: str,
    check_in_date: date,
    check_out_date: date,
    number_of_guests: int,
    number_of_rooms: int,
    purpose: str,
    bill_to_be_settled_by: str,
    preferred_room_type: str = "",
    purpose_details: str = "",
    visitor_email: str = "",
    visitor_organization: str = "",
    visitor_designation: str = "",
    visitor_address: str = "",
    id_proof_type: str = "",
    id_proof_number: str = "",
    project_number: str = "",
    remark: str = "",
    is_offline: bool = False,
    caretaker: ExtraInfo = None,
) -> BookingDetail:
    """
    VH-UC-001: request_booking
    VH-BR-023: Validate booking date consistency / VH-BR-041: Valid dates
    VH-BR-024: Enforce positive quantities
    VH-BR-025: Validate minimum visitor details
    VH-BR-030: Restrict visitor category values
    VH-BR-033: Auto-assign booking creation timestamp
    VH-BR-034: Limit booking remark length
    VH-BR-038: Initial booking status = Pending
    """
    # VH-BR-025: mandatory visitor details
    if not visitor_name or not visitor_phone:
        raise ValidationError("Visitor name and phone are mandatory.")

    # VH-BR-041 / VH-BR-023
    if check_in_date >= check_out_date:
        raise ValidationError("Check-out date must be after check-in date.")
    if check_in_date < date.today():
        raise ValidationError("Check-in date cannot be in the past.")

    # VH-BR-024
    if number_of_guests < 1 or number_of_rooms < 1:
        raise ValidationError("Number of guests and rooms must be at least 1.")

    # VH-BR-034
    if len(remark) > 500:
        raise ValidationError("Remark cannot exceed 500 characters.")

    booking = BookingDetail.objects.create(
        booking_number=_generate_booking_number(),
        intender=intender_extrainfo,
        intender_department=intender_extrainfo.department if hasattr(intender_extrainfo, "department") else None,
        visitor_name=visitor_name,
        visitor_category=visitor_category,
        visitor_phone=visitor_phone,
        visitor_email=visitor_email,
        visitor_organization=visitor_organization,
        visitor_designation=visitor_designation,
        visitor_address=visitor_address,
        id_proof_type=id_proof_type,
        id_proof_number=id_proof_number,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        number_of_guests=number_of_guests,
        number_of_rooms=number_of_rooms,
        preferred_room_type=preferred_room_type,
        purpose=purpose,
        purpose_details=purpose_details,
        bill_to_be_settled_by=bill_to_be_settled_by,
        project_number=project_number,
        remark=remark,
        is_offline=is_offline,
        caretaker=caretaker,
        status=BookingStatus.PENDING,  # VH-BR-038
    )

    # VH-BR-014: notification
    _notify(
        intender_extrainfo.user.pk,
        booking,
        "Booking Request Submitted",
        f"Your booking {booking.booking_number} has been submitted and is pending review.",
    )
    return booking


# ──────────────────────────── UC-003 / WF-VH-008: Modify Booking ────────────────────────────

@transaction.atomic
def modify_booking(
    booking: BookingDetail,
    modified_by: ExtraInfo,
    **kwargs,
) -> BookingDetail:
    """
    UC-VH-017 / VH-UC-003: Modify pending or forwarded booking.
    VH-BR-021: Allow booking modification by VH Staff
    VH-BR-042: Completed bookings immutable
    VH-BR-005: Re-set status to Pending after modification
    """
    if booking.status in [
        BookingStatus.CONFIRMED,
        BookingStatus.CHECKED_IN,
        BookingStatus.CHECKED_OUT,
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ]:
        raise InvalidStatusTransitionError(
            "Cannot modify a booking that is confirmed, checked-in, or completed."
        )  # VH-BR-042

    editable_fields = [
        "visitor_name", "visitor_phone", "visitor_email", "visitor_organization",
        "visitor_designation", "visitor_address", "check_in_date", "check_out_date",
        "number_of_guests", "number_of_rooms", "preferred_room_type", "purpose",
        "purpose_details", "bill_to_be_settled_by", "project_number", "remark",
        "visitor_category", "id_proof_type", "id_proof_number",
    ]
    for field, value in kwargs.items():
        if field in editable_fields:
            setattr(booking, field, value)

    # VH-BR-041
    if booking.check_in_date >= booking.check_out_date:
        raise ValidationError("Check-out date must be after check-in date.")

    # VH-BR-005: re-route to pending after modification
    booking.status = BookingStatus.PENDING
    booking.save()

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Modified",
        f"Your booking {booking.booking_number} has been updated and resubmitted for review.",
    )
    return booking


# ──────────────────────────── UC-018: Review / UC-003: Forward Booking ────────────────────────

@transaction.atomic
def forward_booking(booking: BookingDetail, caretaker: ExtraInfo) -> BookingDetail:
    """
    VH-UC-003 / VH-UC-018: Caretaker reviews and forwards booking.
    VH-BR-039: Pending bookings routed to Caretaker then to Incharge.
    """
    _validate_transition(booking.status, BookingStatus.FORWARDED)
    booking.status = BookingStatus.FORWARDED
    booking.forwarded_by = caretaker
    booking.forwarded_at = timezone.now()
    booking.save()

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Forwarded",
        f"Your booking {booking.booking_number} has been forwarded to VH In-Charge.",
    )
    return booking


@transaction.atomic
def reject_booking_by_caretaker(
    booking: BookingDetail, caretaker: ExtraInfo, reason: str
) -> BookingDetail:
    """Caretaker rejects booking during review."""
    _validate_transition(booking.status, BookingStatus.REJECTED)
    booking.status = BookingStatus.REJECTED
    booking.rejection_reason = reason
    booking.save()

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Rejected",
        f"Your booking {booking.booking_number} was rejected. Reason: {reason}",
    )
    return booking


# ──────────────────────────── UC-004: Confirm Booking ────────────────────────────

@transaction.atomic
def confirm_booking(
    booking: BookingDetail,
    incharge: ExtraInfo,
    room_ids: list,
    remarks: str = "",
) -> BookingDetail:
    """
    VH-UC-004: Approve booking and assign rooms.
    VH-BR-009: VH Incharge authorization
    VH-BR-022: Assign rooms during confirmation
    VH-BR-006: Room status → Occupied
    """
    _validate_transition(booking.status, BookingStatus.CONFIRMED)

    if len(room_ids) != booking.number_of_rooms:
        raise ValidationError(
            f"Please assign exactly {booking.number_of_rooms} room(s)."
        )

    rooms = RoomDetail.objects.filter(pk__in=room_ids, status=RoomStatus.AVAILABLE)
    if rooms.count() != len(room_ids):
        raise RoomNotAvailableError("One or more selected rooms are not available.")

    # VH-BR-012: Verify no overlapping allocations
    from .selectors import get_conflicting_allocations
    conflicts = get_conflicting_allocations(room_ids, booking.check_in_date, booking.check_out_date)
    if conflicts.exists():
        raise RoomNotAvailableError("One or more rooms have conflicting allocations.")

    # Assign rooms
    for room in rooms:
        RoomAllocation.objects.create(
            booking=booking,
            room=room,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            allocated_by=incharge,
        )
        room.status = RoomStatus.OCCUPIED  # VH-BR-006
        room.save()

    booking.status = BookingStatus.CONFIRMED
    booking.approved_by = incharge
    booking.approved_at = timezone.now()
    booking.rejection_reason = remarks
    booking.save()

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Confirmed",
        f"Your booking {booking.booking_number} has been confirmed. Rooms assigned.",
    )
    return booking


@transaction.atomic
def reject_booking_by_incharge(
    booking: BookingDetail, incharge: ExtraInfo, reason: str
) -> BookingDetail:
    """VH-UC-004: Incharge rejects booking."""
    _validate_transition(booking.status, BookingStatus.REJECTED)
    booking.status = BookingStatus.REJECTED
    booking.approved_by = incharge
    booking.approved_at = timezone.now()
    booking.rejection_reason = reason
    booking.save()

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Rejected",
        f"Your booking {booking.booking_number} was rejected. Reason: {reason}",
    )
    return booking


# ──────────────────────────── UC-005 / UC-019 / UC-020: Cancel Booking ────────────────────────

@transaction.atomic
def cancel_booking(
    booking: BookingDetail,
    cancelled_by: ExtraInfo,
    reason: str = "",
) -> BookingDetail:
    """
    VH-UC-005 / VH-UC-019 / VH-UC-020: Cancel booking.
    VH-BR-015: Free rooms when booking cancelled
    VH-BR-016: Create zero bill for cancelled booking
    VH-BR-005: Status → Cancelled
    """
    _validate_transition(booking.status, BookingStatus.CANCELLED)

    booking.status = BookingStatus.CANCELLED
    booking.rejection_reason = reason
    booking.save()

    # VH-BR-015: Release allocated rooms
    for allocation in booking.room_allocations.all():
        room = allocation.room
        room.status = RoomStatus.AVAILABLE  # VH-BR-006
        room.save()
    booking.room_allocations.all().delete()

    # VH-BR-016: Create zero-value bill if not already present
    if not hasattr(booking, "bill") or booking.bill is None:
        Bill.objects.create(
            booking=booking,
            invoice_number=_generate_invoice_number(),
            invoice_date=date.today(),
            room_charges=Decimal("0"),
            meal_charges=Decimal("0"),
            extra_charges=Decimal("0"),
            discount=Decimal("0"),
            total_amount=Decimal("0"),
            amount_paid=Decimal("0"),
            balance_due=Decimal("0"),
            status=BillStatus.CANCELLED,
            billed_to_name=booking.visitor_name,
            generated_by=cancelled_by,
        )

    _notify(
        booking.intender.user.pk,
        booking,
        "Booking Cancelled",
        f"Booking {booking.booking_number} has been cancelled.",
    )
    return booking


# ──────────────────────────── UC-007: Check-in ────────────────────────────

@transaction.atomic
def check_in(
    booking: BookingDetail,
    caretaker: ExtraInfo,
    actual_visitor_details: list = None,
) -> BookingDetail:
    """
    VH-UC-007: Check in visitors.
    VH-BR-017: Accept actual visitor details at check-in
    VH-BR-025: Validate minimum visitor details
    """
    _validate_transition(booking.status, BookingStatus.CHECKED_IN)

    booking.status = BookingStatus.CHECKED_IN
    booking.actual_check_in = timezone.now()
    booking.save()

    # VH-BR-017: Record actual visitor details
    if actual_visitor_details:
        for vd in actual_visitor_details:
            if not vd.get("full_name") or not vd.get("phone"):
                raise ValidationError("Each visitor must have full name and phone.")
            VisitorDetail.objects.create(
                booking=booking,
                full_name=vd.get("full_name"),
                phone=vd.get("phone"),
                email=vd.get("email", ""),
                id_proof_type=vd.get("id_proof_type", ""),
                id_proof_number=vd.get("id_proof_number", ""),
                relationship_to_intender=vd.get("relationship_to_intender", ""),
            )

    _notify(
        booking.intender.user.pk,
        booking,
        "Guest Checked In",
        f"Guests for booking {booking.booking_number} have checked in.",
    )
    return booking


# ──────────────────────────── UC-008: Check-out + Billing ────────────────────────────

@transaction.atomic
def check_out(
    booking: BookingDetail,
    caretaker: ExtraInfo,
    extra_charges: Decimal = Decimal("0"),
    discount: Decimal = Decimal("0"),
    inventory_usage: list = None,
) -> Bill:
    """
    VH-UC-008: Check-out and generate bill.
    VH-BR-001: Calculate room bill by visitor category
    VH-BR-002: Calculate meal bill
    VH-BR-003: Calculate total bill
    VH-BR-018: Update consumable inventory on checkout
    VH-BR-028: One bill per booking
    VH-BR-040: Lock bill after checkout
    """
    _validate_transition(booking.status, BookingStatus.CHECKED_OUT)

    booking.status = BookingStatus.CHECKED_OUT
    booking.actual_check_out = timezone.now()
    booking.save()

    # VH-BR-018: Update inventory usage
    if inventory_usage:
        _process_inventory_usage(booking, caretaker, inventory_usage)

    # VH-BR-001: Room charges
    room_charges = _calculate_room_charges(booking)

    # VH-BR-002: Meal charges
    meal_charges = _calculate_meal_charges(booking)

    # VH-BR-003: Total
    total = room_charges + meal_charges + extra_charges - discount

    # VH-BR-028: ensure single bill
    if hasattr(booking, "bill"):
        raise BillingLockedError("A bill already exists for this booking.")

    bill = Bill.objects.create(
        booking=booking,
        invoice_number=_generate_invoice_number(),
        invoice_date=date.today(),
        room_charges=room_charges,
        meal_charges=meal_charges,
        extra_charges=extra_charges,
        discount=discount,
        total_amount=max(total, Decimal("0")),
        amount_paid=Decimal("0"),
        balance_due=max(total, Decimal("0")),
        status=BillStatus.GENERATED,
        billed_to_name=booking.visitor_name,
        generated_by=caretaker,
    )

    # Free rooms
    for allocation in booking.room_allocations.all():
        room = allocation.room
        room.status = RoomStatus.AVAILABLE  # VH-BR-006
        room.save()

    return bill


def _calculate_room_charges(booking: BookingDetail) -> Decimal:
    """VH-BR-001: Calculate room bill by visitor category."""
    total = Decimal("0")
    num_days = (booking.check_out_date - booking.check_in_date).days or 1
    for allocation in booking.room_allocations.all():
        rate = _get_room_rate(allocation.room, booking.visitor_category)
        total += rate * num_days
    return total


def _calculate_meal_charges(booking: BookingDetail) -> Decimal:
    """VH-BR-002: Aggregate meal charges from meal records."""
    from django.db.models import Sum
    result = booking.meal_bookings.aggregate(total=Sum("total_amount"))
    return result["total"] or Decimal("0")


def _process_inventory_usage(booking, caretaker, usage_list):
    """VH-BR-018: Deduct consumable inventory on checkout."""
    for item_usage in usage_list:
        try:
            item = Inventory.objects.get(pk=item_usage["inventory_id"])
        except Inventory.DoesNotExist:
            continue
        qty = int(item_usage.get("quantity_used", 0))
        if qty <= 0:
            continue
        item.quantity = max(0, item.quantity - qty)
        item.usable_quantity = max(0, item.usable_quantity - qty)
        item.save()
        InventoryUsage.objects.create(
            booking=booking,
            inventory_item=item,
            quantity_used=qty,
            recorded_by=caretaker,
        )
        # VH-BR-020: delete if quantity zero
        if item.quantity == 0:
            item.delete()


# ──────────────────────────── UC-013: Generate Bill ────────────────────────────

@transaction.atomic
def generate_bill(booking: BookingDetail, generated_by: ExtraInfo) -> Bill:
    """
    VH-UC-013: Standalone bill generation (before or at checkout).
    VH-BR-028: One bill per booking.
    """
    if hasattr(booking, "bill"):
        raise BillingLockedError("Bill already exists for this booking.")

    room_charges = _calculate_room_charges(booking)
    meal_charges = _calculate_meal_charges(booking)
    total = room_charges + meal_charges

    bill = Bill.objects.create(
        booking=booking,
        invoice_number=_generate_invoice_number(),
        invoice_date=date.today(),
        room_charges=room_charges,
        meal_charges=meal_charges,
        total_amount=total,
        balance_due=total,
        status=BillStatus.GENERATED,
        billed_to_name=booking.visitor_name,
        generated_by=generated_by,
    )
    return bill


# ──────────────────────────── UC-015: Settle Bill ────────────────────────────

@transaction.atomic
def settle_bill(
    bill: Bill,
    amount: Decimal,
    payment_mode: str,
    received_by: ExtraInfo,
    reference_number: str = "",
    remarks: str = "",
) -> Bill:
    """
    VH-UC-015: Settle bill payment.
    VH-BR-040: Lock bill after completion.
    """
    if bill.status == BillStatus.LOCKED:
        raise BillingLockedError("This bill is locked and cannot be modified.")

    if amount <= 0:
        raise ValidationError("Payment amount must be positive.")

    Payment.objects.create(
        bill=bill,
        amount=amount,
        payment_date=timezone.now(),
        payment_mode=payment_mode,
        reference_number=reference_number,
        received_by=received_by,
        remarks=remarks,
    )

    bill.amount_paid += amount
    bill.balance_due = max(bill.total_amount - bill.amount_paid, Decimal("0"))
    bill.payment_mode = payment_mode
    bill.payment_reference = reference_number
    bill.payment_date = timezone.now()

    if bill.balance_due <= 0:
        bill.status = BillStatus.PAID  # VH-BR-040
    else:
        bill.status = BillStatus.PENDING
    bill.save()
    return bill


# ──────────────────────────── UC-009: Record Meal ────────────────────────────

@transaction.atomic
def record_meal(
    booking: BookingDetail,
    meal_date: date,
    meal_type: str,
    number_of_persons: int,
    rate_per_person: Decimal,
    recorded_by: ExtraInfo,
    vegetarian: bool = True,
    special_requirements: str = "",
) -> MealBooking:
    """
    VH-UC-009: Record meal consumption.
    BR-VH-011: Meal booking deadline enforcement.
    VH-BR-024: Positive quantities.
    """
    if number_of_persons < 1:
        raise ValidationError("Number of persons must be at least 1.")
    if rate_per_person < 0:
        raise ValidationError("Rate cannot be negative.")

    # BR-VH-011: Meal cut-off times
    now = timezone.localtime(timezone.now())
    current_time = now.time()
    if meal_date == date.today():
        from datetime import time as dtime
        if meal_type == MealType.LUNCH and current_time > dtime(9, 0):
            raise MealDeadlineError("Lunch bookings must be placed before 09:00 AM.")
        if meal_type == MealType.DINNER and current_time > dtime(14, 0):
            raise MealDeadlineError("Dinner bookings must be placed before 02:00 PM.")

    total_amount = Decimal(str(number_of_persons)) * rate_per_person

    meal, _ = MealBooking.objects.update_or_create(
        booking=booking,
        meal_date=meal_date,
        meal_type=meal_type,
        defaults={
            "number_of_persons": number_of_persons,
            "vegetarian": vegetarian,
            "special_requirements": special_requirements,
            "rate_per_person": rate_per_person,
            "total_amount": total_amount,
            "recorded_by": recorded_by,
        },
    )
    return meal


# ──────────────────────────── UC-010/011: Inventory ────────────────────────────

@transaction.atomic
def add_inventory_item(
    name: str,
    category: str,
    quantity: int,
    unit: str,
    added_by: ExtraInfo,
    purchase_bill_number: str = "",
    unit_cost: Decimal = Decimal("0"),
    threshold_quantity: int = 5,
    description: str = "",
    usable_quantity: int = None,
    purchase_date: date = None,
) -> Inventory:
    """
    VH-UC-010: Add inventory items.
    VH-BR-024: Enforce positive quantities.
    VH-BR-029: Classify consumable or asset.
    VH-BR-035: Track purchase bill number.
    """
    if quantity < 0:
        raise ValidationError("Quantity cannot be negative.")
    if unit_cost < 0:
        raise ValidationError("Unit cost cannot be negative.")

    usable_quantity = usable_quantity if usable_quantity is not None else quantity

    item = Inventory.objects.create(
        name=name,
        category=category,
        description=description,
        quantity=quantity,
        usable_quantity=usable_quantity,
        unit=unit,
        purchase_bill_number=purchase_bill_number,
        purchase_date=purchase_date or date.today(),
        unit_cost=unit_cost,
        threshold_quantity=threshold_quantity,
        added_by=added_by,
    )
    return item


@transaction.atomic
def update_inventory_item(
    item: Inventory,
    quantity_delta: int,
    updated_by: ExtraInfo,
) -> Inventory:
    """
    VH-UC-011: Update inventory quantities.
    VH-BR-020: Delete when quantity reaches zero.
    VH-BR-019: Recalculate usable stock.
    """
    new_qty = item.quantity + quantity_delta
    if new_qty < 0:
        raise ValidationError("Inventory quantity cannot go below zero.")

    item.quantity = new_qty
    item.usable_quantity = max(0, item.usable_quantity + quantity_delta)
    item.updated_by = updated_by

    if item.quantity == 0:  # VH-BR-020
        item.delete()
        return None

    item.save()
    return item


# ──────────────────────────── UC-006: Room Availability ────────────────────────────

def check_room_availability(
    check_in: date,
    check_out: date,
    room_type: str = None,
    building_id: int = None,
) -> list:
    """
    VH-UC-006 / VH-WF-007: Read-only availability check.
    VH-BR-012: Calculate room availability for date range.
    """
    if check_in >= check_out:
        raise ValidationError("Check-out must be after check-in.")
    if check_in < date.today():
        raise ValidationError("Check-in date cannot be in the past.")

    from .selectors import get_available_rooms
    return get_available_rooms(check_in, check_out, room_type, building_id)


# ──────────────────────────── BR-VH-013: Expire Pending Bookings ────────────────────────────

@transaction.atomic
def expire_pending_bookings():
    """
    VH-BR-013: Automatically expire outdated pending bookings past start date.
    Called by a scheduled task / management command.
    """
    today = date.today()
    expired = BookingDetail.objects.filter(
        status__in=[BookingStatus.PENDING, BookingStatus.FORWARDED],
        check_in_date__lt=today,
    )
    count = 0
    for booking in expired:
        booking.status = BookingStatus.EXPIRED
        booking.save()
        count += 1
    return count


# ──────────────────────────── UC-021: Reports ────────────────────────────

def generate_booking_report(
    start_date: date,
    end_date: date,
    status: str = None,
) -> dict:
    """
    VH-UC-021: Generate reports.
    VH-WF-009 / WF-VH-010
    """
    from .selectors import get_bookings_for_report

    bookings = get_bookings_for_report(start_date, end_date, status)
    total = bookings.count()
    confirmed = bookings.filter(status=BookingStatus.CONFIRMED).count()
    checked_out = bookings.filter(status=BookingStatus.CHECKED_OUT).count()
    cancelled = bookings.filter(status=BookingStatus.CANCELLED).count()

    return {
        "period": {"from": start_date, "to": end_date},
        "total_bookings": total,
        "confirmed": confirmed,
        "checked_out": checked_out,
        "cancelled": cancelled,
        "bookings": bookings,
    }
