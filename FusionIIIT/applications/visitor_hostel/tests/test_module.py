"""
Visitor Hostel Management System (VHMS) - Tests
Tests covering all UCs, BRs, and WFs from functional_requirements.xlsx
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from ..models import (
    Bill, BillStatus, BookingDetail, BookingStatus, Building,
    GuestFeedback, Inventory, InventoryCategory, MealBooking, MealType,
    Notification, RoomAllocation, RoomDetail, RoomFloor, RoomStatus,
    RoomType, VisitorCategory, VisitorDetail,
)
from ..services import (
    VHError, InvalidStatusTransitionError, RoomNotAvailableError,
    BillingLockedError, ValidationError as VHValidationError,
    MealDeadlineError,
    add_inventory_item, cancel_booking, check_in, check_out,
    check_room_availability, confirm_booking, create_booking,
    expire_pending_bookings, forward_booking, generate_bill,
    modify_booking, record_meal, reject_booking_by_caretaker,
    reject_booking_by_incharge, settle_bill, update_inventory_item,
)
from ..selectors import (
    get_all_bookings, get_all_inventory, get_available_rooms,
    get_bill_by_booking, get_booking_by_id, get_bookings_by_intender,
    get_dashboard_stats, get_forwarded_bookings, get_low_stock_items,
    get_pending_bookings,
)


# ──────────────────────────── Test Setup Helpers ────────────────────────────

def make_user(username="testuser", password="pass1234"):
    return User.objects.create_user(username=username, password=password,
                                    first_name="Test", last_name="User",
                                    email=f"{username}@iiitdmj.ac.in")


def make_extrainfo(user, user_type="faculty"):
    """Create ExtraInfo-like mock using a simple dict + patching."""
    from applications.globals.models import ExtraInfo
    # We use get_or_create so tests don't fail if ExtraInfo already exists.
    from django.contrib.auth.models import User
    ei, _ = ExtraInfo.objects.get_or_create(
        user=user,
        defaults={"user_type": user_type}
    )
    return ei


def make_building(code="GH1"):
    return Building.objects.get_or_create(
        code=code,
        defaults={"name": f"Guest House {code}", "location": "Campus"}
    )[0]


def make_room(building, room_number="101", room_type=RoomType.SINGLE):
    return RoomDetail.objects.get_or_create(
        building=building,
        room_number=room_number,
        defaults={
            "room_type": room_type,
            "floor": RoomFloor.GROUND,
            "tariff_per_day": Decimal("500"),
            "tariff_faculty": Decimal("300"),
            "tariff_staff": Decimal("350"),
            "tariff_student": Decimal("200"),
            "tariff_external": Decimal("600"),
        },
    )[0]


def make_booking(intender_ei, days_ahead=3, status=BookingStatus.PENDING):
    check_in = date.today() + timedelta(days=days_ahead)
    check_out = check_in + timedelta(days=2)
    b = BookingDetail.objects.create(
        booking_number=f"VHTEST{BookingDetail.objects.count():04d}",
        intender=intender_ei,
        visitor_name="John Visitor",
        visitor_category=VisitorCategory.IIIT_FACULTY,
        visitor_phone="9999999999",
        check_in_date=check_in,
        check_out_date=check_out,
        number_of_guests=1,
        number_of_rooms=1,
        purpose="Academic",
        bill_to_be_settled_by="Intender",
        status=status,
    )
    return b


# ──────────────────────────── Model Unit Tests ────────────────────────────

class RoomDetailModelTest(TestCase):
    """VH-BR-027, VH-BR-031, VH-BR-032"""

    def setUp(self):
        self.building = make_building()

    def test_unique_room_number_per_building(self):
        """VH-BR-027: Enforce unique room numbers"""
        make_room(self.building, "101")
        with self.assertRaises(Exception):
            RoomDetail.objects.create(
                building=self.building,
                room_number="101",
                room_type=RoomType.DOUBLE,
                tariff_per_day=Decimal("500"),
            )

    def test_room_type_choices(self):
        """VH-BR-031"""
        room = make_room(self.building, "102")
        self.assertIn(room.room_type, [c[0] for c in RoomType.choices])

    def test_floor_choices(self):
        """VH-BR-032"""
        room = make_room(self.building, "103")
        self.assertIn(room.floor, [c[0] for c in RoomFloor.choices])


class BookingDetailModelTest(TestCase):
    """VH-BR-033, VH-BR-030, VH-BR-034"""

    def setUp(self):
        self.user = make_user("bookingtest")
        self.ei = make_extrainfo(self.user)

    def test_auto_assign_booking_timestamp(self):
        """VH-BR-033"""
        b = make_booking(self.ei)
        self.assertIsNotNone(b.booking_date)

    def test_visitor_category_choices(self):
        """VH-BR-030"""
        b = make_booking(self.ei)
        valid = [c[0] for c in VisitorCategory.choices]
        self.assertIn(b.visitor_category, valid)

    def test_bill_one_to_one_constraint(self):
        """VH-BR-028"""
        b = make_booking(self.ei)
        Bill.objects.create(
            booking=b, invoice_number="INV001", invoice_date=date.today(),
            total_amount=Decimal("0"), status=BillStatus.GENERATED,
        )
        with self.assertRaises(Exception):
            Bill.objects.create(
                booking=b, invoice_number="INV002", invoice_date=date.today(),
                total_amount=Decimal("0"), status=BillStatus.GENERATED,
            )


# ──────────────────────────── Service Tests ────────────────────────────

class CreateBookingServiceTest(TestCase):
    """VH-UC-001: request_booking"""

    def setUp(self):
        self.user = make_user("indenter1")
        self.ei = make_extrainfo(self.user)

    def test_create_booking_success(self):
        """VH-BR-038: initial status Pending"""
        booking = create_booking(
            intender_extrainfo=self.ei,
            visitor_name="Jane Guest",
            visitor_category=VisitorCategory.IIIT_FACULTY,
            visitor_phone="8888888888",
            check_in_date=date.today() + timedelta(days=3),
            check_out_date=date.today() + timedelta(days=5),
            number_of_guests=1,
            number_of_rooms=1,
            purpose="Academic",
            bill_to_be_settled_by="Intender",
        )
        self.assertEqual(booking.status, BookingStatus.PENDING)
        self.assertTrue(booking.booking_number.startswith("VH"))

    def test_invalid_dates(self):
        """VH-BR-041 / VH-BR-023"""
        with self.assertRaises(VHValidationError):
            create_booking(
                intender_extrainfo=self.ei,
                visitor_name="X",
                visitor_category=VisitorCategory.IIIT_FACULTY,
                visitor_phone="111",
                check_in_date=date.today() + timedelta(days=5),
                check_out_date=date.today() + timedelta(days=3),
                number_of_guests=1,
                number_of_rooms=1,
                purpose="Academic",
                bill_to_be_settled_by="Intender",
            )

    def test_past_check_in_rejected(self):
        """VH-BR-023"""
        with self.assertRaises(VHValidationError):
            create_booking(
                intender_extrainfo=self.ei,
                visitor_name="X",
                visitor_category=VisitorCategory.IIIT_FACULTY,
                visitor_phone="111",
                check_in_date=date.today() - timedelta(days=2),
                check_out_date=date.today() + timedelta(days=1),
                number_of_guests=1,
                number_of_rooms=1,
                purpose="Academic",
                bill_to_be_settled_by="Intender",
            )

    def test_missing_visitor_details_rejected(self):
        """VH-BR-025"""
        with self.assertRaises(VHValidationError):
            create_booking(
                intender_extrainfo=self.ei,
                visitor_name="",  # empty
                visitor_category=VisitorCategory.IIIT_FACULTY,
                visitor_phone="",
                check_in_date=date.today() + timedelta(days=2),
                check_out_date=date.today() + timedelta(days=4),
                number_of_guests=1,
                number_of_rooms=1,
                purpose="Academic",
                bill_to_be_settled_by="Intender",
            )

    def test_remark_length_limit(self):
        """VH-BR-034"""
        with self.assertRaises(VHValidationError):
            create_booking(
                intender_extrainfo=self.ei,
                visitor_name="X",
                visitor_category=VisitorCategory.IIIT_FACULTY,
                visitor_phone="111",
                check_in_date=date.today() + timedelta(days=2),
                check_out_date=date.today() + timedelta(days=4),
                number_of_guests=1,
                number_of_rooms=1,
                purpose="Academic",
                bill_to_be_settled_by="Intender",
                remark="X" * 501,
            )

    def test_zero_guests_rejected(self):
        """VH-BR-024"""
        with self.assertRaises(VHValidationError):
            create_booking(
                intender_extrainfo=self.ei,
                visitor_name="X",
                visitor_category=VisitorCategory.IIIT_FACULTY,
                visitor_phone="111",
                check_in_date=date.today() + timedelta(days=2),
                check_out_date=date.today() + timedelta(days=4),
                number_of_guests=0,  # invalid
                number_of_rooms=1,
                purpose="Academic",
                bill_to_be_settled_by="Intender",
            )


class BookingStatusLifecycleTest(TestCase):
    """VH-BR-005: Booking status lifecycle transitions"""

    def setUp(self):
        self.user = make_user("lifecycle")
        self.ei = make_extrainfo(self.user)
        self.building = make_building("LCT")
        self.room = make_room(self.building, "201")

    def test_forward_booking(self):
        """VH-UC-003: Forward to Incharge"""
        booking = make_booking(self.ei)
        updated = forward_booking(booking, self.ei)
        self.assertEqual(updated.status, BookingStatus.FORWARDED)

    def test_invalid_transition_raises(self):
        """VH-BR-005 / VH-BR-007"""
        booking = make_booking(self.ei, status=BookingStatus.CHECKED_OUT)
        with self.assertRaises(InvalidStatusTransitionError):
            cancel_booking(booking, self.ei)

    def test_confirm_booking(self):
        """VH-UC-004 / VH-BR-022"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        updated = confirm_booking(booking, self.ei, [self.room.pk])
        self.assertEqual(updated.status, BookingStatus.CONFIRMED)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, RoomStatus.OCCUPIED)

    def test_reject_booking_by_incharge(self):
        """VH-UC-004: Reject"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        updated = reject_booking_by_incharge(booking, self.ei, "No rooms")
        self.assertEqual(updated.status, BookingStatus.REJECTED)

    def test_full_lifecycle(self):
        """WF-VH-001: Pending → Forward → Confirm → CheckIn → CheckOut"""
        booking = make_booking(self.ei)
        booking = forward_booking(booking, self.ei)
        booking = confirm_booking(booking, self.ei, [self.room.pk])
        booking = check_in(booking, self.ei)
        self.assertEqual(booking.status, BookingStatus.CHECKED_IN)
        bill = check_out(booking, self.ei)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CHECKED_OUT)
        self.assertIsNotNone(bill)


class CancelBookingServiceTest(TestCase):
    """VH-UC-005 / VH-BR-015 / VH-BR-016"""

    def setUp(self):
        self.user = make_user("canceluser")
        self.ei = make_extrainfo(self.user)
        self.building = make_building("CBL")
        self.room = make_room(self.building, "301")

    def test_cancel_confirmed_booking_frees_rooms(self):
        """VH-BR-015"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        confirm_booking(booking, self.ei, [self.room.pk])
        booking.refresh_from_db()
        cancel_booking(booking, self.ei, "Change of plans")
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

    def test_cancel_creates_zero_bill(self):
        """VH-BR-016"""
        booking = make_booking(self.ei)
        cancel_booking(booking, self.ei)
        booking.refresh_from_db()
        bill = Bill.objects.get(booking=booking)
        self.assertEqual(bill.total_amount, Decimal("0"))
        self.assertEqual(bill.status, BillStatus.CANCELLED)


class ModifyBookingServiceTest(TestCase):
    """UC-VH-017 / VH-BR-021 / VH-BR-042"""

    def setUp(self):
        self.user = make_user("modifyuser")
        self.ei = make_extrainfo(self.user)
        self.other_user = make_user("modifyuser2")
        self.other_ei = make_extrainfo(self.other_user)

    def test_modify_pending_booking(self):
        """VH-BR-021"""
        booking = make_booking(self.ei)
        updated = modify_booking(
            booking, self.ei,
            visitor_name="Updated Name",
            visitor_phone="7777777777",
        )
        self.assertEqual(updated.visitor_name, "Updated Name")
        self.assertEqual(updated.status, BookingStatus.PENDING)

    def test_cannot_modify_confirmed(self):
        """VH-BR-042"""
        booking = make_booking(self.ei, status=BookingStatus.CONFIRMED)
        with self.assertRaises(InvalidStatusTransitionError):
            modify_booking(booking, self.ei, visitor_name="X")

    def test_cannot_modify_forwarded_booking(self):
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        with self.assertRaises(InvalidStatusTransitionError):
            modify_booking(booking, self.ei, visitor_name="X")

    def test_non_intender_cannot_modify(self):
        booking = make_booking(self.ei)
        with self.assertRaises(VHError):
            modify_booking(booking, self.other_ei, visitor_name="X")


class CheckInServiceTest(TestCase):
    """VH-UC-007 / VH-BR-017"""

    def setUp(self):
        self.user = make_user("checkinuser")
        self.ei = make_extrainfo(self.user)
        self.building = make_building("CKI")
        self.room = make_room(self.building, "401")

    def test_check_in_records_visitor_details(self):
        """VH-BR-017"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        confirm_booking(booking, self.ei, [self.room.pk])
        booking.refresh_from_db()
        updated = check_in(
            booking, self.ei,
            actual_visitor_details=[
                {"full_name": "John Visitor", "phone": "9000000000",
                 "id_proof_type": "Aadhar", "id_proof_number": "1234"}
            ],
        )
        self.assertEqual(updated.status, BookingStatus.CHECKED_IN)
        self.assertEqual(VisitorDetail.objects.filter(booking=booking).count(), 1)

    def test_check_in_invalid_visitor_detail(self):
        """VH-BR-025"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        confirm_booking(booking, self.ei, [self.room.pk])
        booking.refresh_from_db()
        with self.assertRaises(VHValidationError):
            check_in(
                booking, self.ei,
                actual_visitor_details=[{"full_name": "", "phone": ""}],
            )


class BillingServiceTest(TestCase):
    """VH-UC-013/014/015 / VH-BR-001/002/003/028/040"""

    def setUp(self):
        self.user = make_user("billuser")
        self.ei = make_extrainfo(self.user)
        self.building = make_building("BLG")
        self.room = make_room(self.building, "501")

    def _make_confirmed_booking(self):
        b = make_booking(self.ei, status=BookingStatus.FORWARDED)
        confirm_booking(b, self.ei, [self.room.pk])
        b.refresh_from_db()
        check_in(b, self.ei)
        b.refresh_from_db()
        return b

    def test_checkout_generates_bill(self):
        """VH-BR-001/002/003"""
        booking = self._make_confirmed_booking()
        bill = check_out(booking, self.ei)
        self.assertIsNotNone(bill)
        self.assertGreaterEqual(bill.room_charges, Decimal("0"))
        self.assertEqual(bill.total_amount, bill.room_charges + bill.meal_charges + bill.extra_charges - bill.discount)

    def test_checkout_includes_overstay_in_extra_charges(self):
        """VH-UC-008: Overstay amount should be reflected in extras on bill."""
        booking = self._make_confirmed_booking()
        bill = check_out(
            booking,
            self.ei,
            extra_charges=Decimal("120"),
            overstay_hours=3,
            overstay_charges=Decimal("450"),
        )
        self.assertEqual(bill.extra_charges, Decimal("570"))
        self.assertEqual(bill.total_amount, bill.room_charges + bill.meal_charges + Decimal("570") - bill.discount)

    def test_one_bill_per_booking(self):
        """VH-BR-028"""
        booking = self._make_confirmed_booking()
        check_out(booking, self.ei)
        booking.refresh_from_db()
        with self.assertRaises(Exception):
            check_out(booking, self.ei)

    def test_settle_bill(self):
        """VH-UC-015 / VH-BR-040"""
        booking = self._make_confirmed_booking()
        bill = check_out(booking, self.ei)
        settled = settle_bill(bill, bill.total_amount or Decimal("100"), "Cash", self.ei)
        self.assertIn(settled.status, [BillStatus.PAID, BillStatus.PENDING])

    def test_locked_bill_cannot_be_modified(self):
        """VH-BR-040"""
        booking = self._make_confirmed_booking()
        bill = check_out(booking, self.ei)
        bill.status = BillStatus.LOCKED
        bill.save()
        with self.assertRaises(BillingLockedError):
            settle_bill(bill, Decimal("100"), "Cash", self.ei)


class MealServiceTest(TestCase):
    """VH-UC-009 / BR-VH-011 / VH-BR-002"""

    def setUp(self):
        self.user = make_user("mealuser")
        self.ei = make_extrainfo(self.user)
        self.booking = make_booking(self.ei, status=BookingStatus.CHECKED_IN)

    def test_record_meal(self):
        meal = record_meal(
            booking=self.booking,
            meal_date=self.booking.check_in_date,
            meal_type=MealType.DINNER,
            number_of_persons=2,
            rate_per_person=Decimal("100"),
            recorded_by=self.ei,
        )
        self.assertEqual(meal.total_amount, Decimal("200"))

    def test_invalid_meal_persons(self):
        """VH-BR-024"""
        with self.assertRaises(VHValidationError):
            record_meal(
                booking=self.booking,
                meal_date=self.booking.check_in_date,
                meal_type=MealType.LUNCH,
                number_of_persons=0,
                rate_per_person=Decimal("100"),
                recorded_by=self.ei,
            )


class InventoryServiceTest(TestCase):
    """VH-UC-010/011/012 / VH-BR-019/020/029/035"""

    def setUp(self):
        self.user = make_user("invuser")
        self.ei = make_extrainfo(self.user)

    def test_add_inventory_item(self):
        """VH-UC-010 / VH-BR-029 / VH-BR-035"""
        item = add_inventory_item(
            name="Bed Sheet",
            category=InventoryCategory.CONSUMABLE,
            quantity=50,
            unit="piece",
            added_by=self.ei,
            purchase_bill_number="PB-2024-001",
        )
        self.assertEqual(item.quantity, 50)
        self.assertEqual(item.purchase_bill_number, "PB-2024-001")

    def test_update_inventory(self):
        """VH-UC-011 / VH-BR-019"""
        item = add_inventory_item(
            name="Towel",
            category=InventoryCategory.ASSET,
            quantity=10,
            unit="piece",
            added_by=self.ei,
        )
        updated = update_inventory_item(item, 5, self.ei)
        self.assertEqual(updated.quantity, 15)

    def test_inventory_delete_at_zero(self):
        """VH-BR-020"""
        item = add_inventory_item(
            name="Soap",
            category=InventoryCategory.CONSUMABLE,
            quantity=2,
            unit="bar",
            added_by=self.ei,
        )
        result = update_inventory_item(item, -2, self.ei)
        self.assertIsNone(result)

    def test_negative_quantity_rejected(self):
        """VH-BR-024"""
        item = add_inventory_item(
            name="Shampoo",
            category=InventoryCategory.CONSUMABLE,
            quantity=5,
            unit="bottle",
            added_by=self.ei,
        )
        with self.assertRaises(VHValidationError):
            update_inventory_item(item, -10, self.ei)


class RoomAvailabilityServiceTest(TestCase):
    """VH-UC-006 / VH-BR-012 / VH-WF-007"""

    def setUp(self):
        self.user = make_user("availuser")
        self.ei = make_extrainfo(self.user)
        self.building = make_building("AVL")
        self.room1 = make_room(self.building, "101")
        self.room2 = make_room(self.building, "102")

    def test_available_rooms_returned(self):
        """VH-BR-012"""
        ci = date.today() + timedelta(days=2)
        co = date.today() + timedelta(days=4)
        rooms = list(check_room_availability(ci, co))
        self.assertGreaterEqual(len(rooms), 2)

    def test_occupied_rooms_excluded(self):
        """VH-BR-012: Occupied rooms not shown"""
        booking = make_booking(self.ei, status=BookingStatus.FORWARDED)
        booking.check_in_date = date.today() + timedelta(days=2)
        booking.check_out_date = date.today() + timedelta(days=5)
        booking.save()
        confirm_booking(booking, self.ei, [self.room1.pk])
        ci = date.today() + timedelta(days=3)
        co = date.today() + timedelta(days=4)
        available = list(check_room_availability(ci, co))
        room_ids = [r.pk for r in available]
        self.assertNotIn(self.room1.pk, room_ids)


class ExpirePendingBookingsTest(TestCase):
    """VH-BR-013"""

    def setUp(self):
        self.user = make_user("expireuser")
        self.ei = make_extrainfo(self.user)

    def test_expire_past_pending_bookings(self):
        b = BookingDetail.objects.create(
            booking_number="VHEXP0001",
            intender=self.ei,
            visitor_name="Expiring Guest",
            visitor_category=VisitorCategory.IIIT_FACULTY,
            visitor_phone="111",
            check_in_date=date.today() - timedelta(days=3),
            check_out_date=date.today() - timedelta(days=1),
            number_of_guests=1,
            number_of_rooms=1,
            purpose="Academic",
            bill_to_be_settled_by="Intender",
            status=BookingStatus.PENDING,
        )
        count = expire_pending_bookings()
        self.assertGreaterEqual(count, 1)
        b.refresh_from_db()
        self.assertEqual(b.status, BookingStatus.EXPIRED)


class SelectorTest(TestCase):
    """Selector layer tests"""

    def setUp(self):
        self.user = make_user("selectoruser")
        self.ei = make_extrainfo(self.user)

    def test_get_pending_bookings(self):
        make_booking(self.ei, status=BookingStatus.PENDING)
        pending = get_pending_bookings()
        self.assertGreaterEqual(pending.count(), 1)

    def test_get_dashboard_stats(self):
        stats = get_dashboard_stats()
        self.assertIn("total_bookings", stats)
        self.assertIn("available_rooms", stats)
        self.assertIn("low_stock_items", stats)

    def test_get_low_stock_items(self):
        """BR-VH-007"""
        user = make_user("stockuser2")
        ei = make_extrainfo(user)
        item = add_inventory_item(
            name="Low Item", category=InventoryCategory.CONSUMABLE,
            quantity=2, unit="pc", added_by=ei,
            threshold_quantity=10,
        )
        low = list(get_low_stock_items())
        names = [i.name for i in low]
        self.assertIn("Low Item", names)


# ──────────────────────────── API Integration Tests ────────────────────────────

class BookingAPITest(APITestCase):
    """API endpoint integration tests"""

    def setUp(self):
        self.user = make_user("apiuser")
        self.ei = make_extrainfo(self.user)
        self.client.force_authenticate(user=self.user)
        self.building = make_building("API")
        self.room = make_room(self.building, "601")
        self.other_user = make_user("apiother")
        self.other_ei = make_extrainfo(self.other_user)

    def test_get_dashboard(self):
        """VH-UC-016"""
        response = self.client.get("/api/visitorhostel/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_bookings", response.data)

    def test_create_booking_api(self):
        """VH-UC-001"""
        payload = {
            "visitor_name": "API Guest",
            "visitor_category": VisitorCategory.IIIT_FACULTY,
            "visitor_phone": "9876543210",
            "check_in_date": str(date.today() + timedelta(days=3)),
            "check_out_date": str(date.today() + timedelta(days=5)),
            "number_of_guests": 1,
            "number_of_rooms": 1,
            "purpose": "Academic",
            "bill_to_be_settled_by": "Intender",
        }
        response = self.client.post("/api/visitorhostel/bookings/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], BookingStatus.PENDING)

    def test_create_booking_invalid_dates(self):
        """VH-BR-041"""
        payload = {
            "visitor_name": "Test",
            "visitor_category": VisitorCategory.IIIT_FACULTY,
            "visitor_phone": "111",
            "check_in_date": str(date.today() + timedelta(days=5)),
            "check_out_date": str(date.today() + timedelta(days=3)),
            "number_of_guests": 1,
            "number_of_rooms": 1,
            "purpose": "Academic",
            "bill_to_be_settled_by": "Intender",
        }
        response = self.client.post("/api/visitorhostel/bookings/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_room_availability_api(self):
        """VH-UC-006"""
        ci = date.today() + timedelta(days=2)
        co = date.today() + timedelta(days=4)
        response = self.client.get(
            f"/api/visitorhostel/rooms/availability/?check_in_date={ci}&check_out_date={co}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_access_denied(self):
        """VH-BR-011"""
        unauth_client = APIClient()
        response = unauth_client.get("/api/visitorhostel/bookings/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inventory_add_api(self):
        """VH-UC-010"""
        payload = {
            "name": "New Item",
            "category": InventoryCategory.CONSUMABLE,
            "quantity": 10,
            "unit": "piece",
            "threshold_quantity": 3,
        }
        response = self.client.post("/api/visitorhostel/inventory/add/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["quantity"], 10)

    def test_low_stock_api(self):
        """BR-VH-007"""
        response = self.client.get("/api/visitorhostel/inventory/low-stock/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cancel_booking_api(self):
        """VH-UC-005: intender requests cancellation"""
        booking = make_booking(self.ei)
        response = self.client.post(
            "/api/visitorhostel/bookings/cancel/",
            {"booking_id": booking.pk, "reason": "Test cancel"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], BookingStatus.CANCELLATION_REQUESTED)

    def test_cancel_preview_api(self):
        booking = make_booking(self.ei)
        response = self.client.post(
            "/api/visitorhostel/bookings/cancel/preview/",
            {"booking_id": booking.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cancellation_charge", response.data)
        self.assertIn("penalty_percent", response.data)

    def test_caretaker_approves_cancellation_request(self):
        booking = make_booking(self.ei)
        self.client.post(
            "/api/visitorhostel/bookings/cancel/",
            {"booking_id": booking.pk, "reason": "Need to cancel"},
            format="json",
        )

        self.other_ei.last_selected_role = "VhCaretaker"
        self.other_ei.save(update_fields=["last_selected_role"])
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(
            "/api/visitorhostel/bookings/cancel/approve/",
            {"booking_id": booking.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], BookingStatus.CANCELLED)

    def test_forward_booking_api(self):
        """VH-UC-003"""
        booking = make_booking(self.ei)
        response = self.client.post(
            "/api/visitorhostel/bookings/forward/",
            {"booking_id": booking.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], BookingStatus.FORWARDED)

    def test_report_api(self):
        """VH-UC-021"""
        start = str(date.today() - timedelta(days=7))
        end = str(date.today())
        response = self.client.get(f"/api/visitorhostel/reports/?start_date={start}&end_date={end}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_bookings", response.data)

    def test_booking_detail_visible_to_intender(self):
        booking = make_booking(self.ei)
        response = self.client.get(f"/api/visitorhostel/bookings/{booking.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], booking.pk)

    def test_booking_detail_hidden_from_other_intender(self):
        booking = make_booking(self.ei)
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/visitorhostel/bookings/{booking.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_detail_visible_to_vh_caretaker(self):
        booking = make_booking(self.ei)
        self.other_ei.last_selected_role = "VhCaretaker"
        self.other_ei.save(update_fields=["last_selected_role"])
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/visitorhostel/bookings/{booking.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], booking.pk)

    def test_booking_detail_visible_to_plain_incharge_role(self):
        booking = make_booking(self.ei)
        self.other_ei.last_selected_role = "incharge"
        self.other_ei.save(update_fields=["last_selected_role"])
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/visitorhostel/bookings/{booking.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], booking.pk)
