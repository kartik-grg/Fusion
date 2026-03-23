"""
Management command: seed_visitor_hostel
Seeds the visitor hostel tables with mock data for testing.
Run: python manage.py seed_visitor_hostel
      python manage.py seed_visitor_hostel --clear  (wipe & re-seed)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import datetime

from applications.globals.models import ExtraInfo, DepartmentInfo, Faculty, Staff
from applications.visitor_hostel.models import (
    Building, RoomDetail, BookingDetail, RoomAllocation,
    Bill, MealBooking, Inventory,
    BookingStatus, RoomStatus, RoomType, RoomFloor,
    VisitorCategory, PurposeType, BillSettledBy, BillStatus,
    PaymentMode, MealType, InventoryCategory,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _extra(username):
    return ExtraInfo.objects.get(user__username=username)


def _dept(name):
    return DepartmentInfo.objects.get(name=name)


# ── command ────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed visitor hostel tables with mock data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing visitor hostel data before seeding'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing visitor hostel data ...')
            MealBooking.objects.all().delete()
            Bill.objects.all().delete()
            RoomAllocation.objects.all().delete()
            BookingDetail.objects.all().delete()
            RoomDetail.objects.all().delete()
            Building.objects.all().delete()
            Inventory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared.'))

        with transaction.atomic():
            self._seed_building_and_rooms()
            self._seed_bookings()
            self._seed_bills()
            self._seed_meals()
            self._seed_inventory()

        self.stdout.write(self.style.SUCCESS('Visitor hostel mock data seeded successfully.'))

    # ── Building & Rooms ───────────────────────────────────────────────────

    def _seed_building_and_rooms(self):
        building, created = Building.objects.get_or_create(
            code='VH-A',
            defaults={
                'name': 'Visitor Hostel',
                'location': 'IIITDMJ Campus',
                'total_rooms': 16,
                'description': 'Main visitor hostel building',
                'contact_number': '0761-2794158',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created building: {building}')
        else:
            self.stdout.write(f'  Building already exists: {building}')

        rooms = [
            # (room_num, type,     floor, has_ac, has_bath, status,      tariff)
            ('101', 'Single', 0, True,  True,  'Occupied',    900),
            ('102', 'Single', 0, True,  True,  'Occupied',    900),
            ('103', 'Single', 0, True,  True,  'Available',   900),
            ('104', 'Single', 0, True,  True,  'Occupied',    900),
            ('105', 'Single', 0, False, True,  'Occupied',    900),
            ('106', 'Double', 0, True,  True,  'Available',  1500),
            ('107', 'Double', 0, True,  True,  'Available',  1500),
            ('108', 'Double', 0, True,  True,  'Maintenance', 1500),
            ('201', 'Single', 1, True,  True,  'Available',   900),
            ('202', 'Single', 1, True,  True,  'Available',   900),
            ('203', 'Double', 1, True,  True,  'Occupied',   1500),
            ('204', 'Double', 1, True,  True,  'Occupied',   1500),
            ('205', 'Single', 1, False, True,  'Available',   900),
            ('206', 'Single', 1, False, False, 'Available',   900),
            ('S01', 'Suite',  2, True,  True,  'Occupied',   3000),
            ('S02', 'Suite',  2, True,  True,  'Available',  3000),
        ]

        for (num, rtype, floor, ac, bath, status, tariff) in rooms:
            obj, created = RoomDetail.objects.get_or_create(
                building=building,
                room_number=num,
                defaults={
                    'room_type': rtype,
                    'floor': floor,
                    'has_ac': ac,
                    'has_attached_bathroom': bath,
                    'status': status,
                    'tariff_per_day': tariff,
                    'bed_count': 2 if rtype == 'Double' else (3 if rtype == 'Suite' else 1),
                    'max_occupancy': 2 if rtype in ('Double', 'Suite') else 1,
                }
            )
            if created:
                self.stdout.write(f'  Created room: {obj}')

    # ── Bookings ───────────────────────────────────────────────────────────

    def _seed_bookings(self):
        # Intender mapping (using actual faculty/staff in the DB)
        # "Prof. A. Jain (CSE)"  → atul (Prof. Atul Gupta, CSE)
        # "Dr. R. Sharma (ECE)"  → anilk (Dr. Anil Kumar, ECE)
        # "Mr. S. Kumar (Staff)" → ak (Mr. Anup Kumar Gupta, Staff)
        # "Self"                 → aojha (Prof. Aparajita Ojha, CSE)

        intender_map = {
            'Prof. A. Jain (CSE)':  'atul',
            'Dr. R. Sharma (ECE)':  'anilk',
            'Mr. S. Kumar (Staff)': 'ak',
            'Self':                 'aojha',
        }
        category_map = {
            'Official Visitor': VisitorCategory.OFFICIAL,
            'Guest Speaker':    VisitorCategory.GUEST_SPEAKER,
            'IIIT Faculty':     VisitorCategory.IIIT_FACULTY,
            'Personal Guest':   VisitorCategory.PERSONAL,
            'Examiner':         VisitorCategory.EXAMINER,
        }
        purpose_map = {
            'Official Work': PurposeType.OFFICIAL,
            'Conference':    PurposeType.CONFERENCE,
            'Academic':      PurposeType.ACADEMIC,
            'Recruitment':   PurposeType.RECRUITMENT,
            'Personal':      PurposeType.PERSONAL,
        }
        billing_map = {
            'Department': BillSettledBy.DEPARTMENT,
            'Institute':  BillSettledBy.INSTITUTE,
            'Intender':   BillSettledBy.INTENDER,
            'Guest':      BillSettledBy.GUEST,
        }
        caretaker = _extra('nhcaretaker')

        bookings_data = [
            {
                'booking_number': 'VH20240301',
                'visitor_name': 'Dr. Rajesh Kumar',
                'visitor_org': 'IIT Delhi',
                'category': 'Official Visitor',
                'checkin': '2024-03-15',
                'checkout': '2024-03-17',
                'rooms': 1, 'guests': 1,
                'purpose': 'Official Work',
                'phone': '9876543210',
                'email': 'rajesh@iitd.ac.in',
                'intender_key': 'Prof. A. Jain (CSE)',
                'bill_to': 'Department',
                'status': BookingStatus.FORWARDED,
                'remark': 'Guest speaker for conference',
            },
            {
                'booking_number': 'VH20240302',
                'visitor_name': 'Prof. Meena Shah',
                'visitor_org': 'NIT Bhopal',
                'category': 'Guest Speaker',
                'checkin': '2024-03-18',
                'checkout': '2024-03-21',
                'rooms': 2, 'guests': 2,
                'purpose': 'Conference',
                'phone': '9765432109',
                'email': 'meena@nit.ac.in',
                'intender_key': 'Dr. R. Sharma (ECE)',
                'bill_to': 'Institute',
                'status': BookingStatus.PENDING,
                'remark': '',
            },
            {
                'booking_number': 'VH20240303',
                'visitor_name': 'Mr. Arun Verma',
                'visitor_org': 'DRDO',
                'category': 'Official Visitor',
                'checkin': '2024-03-20',
                'checkout': '2024-03-21',
                'rooms': 1, 'guests': 1,
                'purpose': 'Official Work',
                'phone': '9654321098',
                'email': 'arun@drdo.gov.in',
                'intender_key': 'Prof. A. Jain (CSE)',
                'bill_to': 'Intender',
                'status': BookingStatus.PENDING,
                'remark': 'Arriving by evening train',
            },
            {
                'booking_number': 'VH20240289',
                'visitor_name': 'Dr. T. Mishra',
                'visitor_org': 'IIIT',
                'category': 'IIIT Faculty',
                'checkin': '2024-03-12',
                'checkout': '2024-03-14',
                'rooms': 1, 'guests': 1,
                'purpose': 'Academic',
                'phone': '9543210987',
                'email': 'tmishra@iiitdmj.ac.in',
                'intender_key': 'Self',
                'bill_to': 'Intender',
                'status': BookingStatus.CHECKED_IN,
                'remark': '',
            },
            {
                'booking_number': 'VH20240291',
                'visitor_name': 'Prof. N. Singh',
                'visitor_org': 'IIIT',
                'category': 'IIIT Faculty',
                'checkin': '2024-03-11',
                'checkout': '2024-03-16',
                'rooms': 1, 'guests': 2,
                'purpose': 'Academic',
                'phone': '9432109876',
                'email': 'nsingh@iiitdmj.ac.in',
                'intender_key': 'Self',
                'bill_to': 'Department',
                'status': BookingStatus.CONFIRMED,
                'remark': '',
            },
            {
                'booking_number': 'VH20240294',
                'visitor_name': 'Mr. P. Joshi',
                'visitor_org': 'DRDO',
                'category': 'Official Visitor',
                'checkin': '2024-03-13',
                'checkout': '2024-03-17',
                'rooms': 1, 'guests': 1,
                'purpose': 'Official Work',
                'phone': '9321098765',
                'email': 'pjoshi@drdo.gov.in',
                'intender_key': 'Dr. R. Sharma (ECE)',
                'bill_to': 'Department',
                'status': BookingStatus.CHECKED_IN,
                'remark': '',
            },
            {
                'booking_number': 'VH20240280',
                'visitor_name': 'Ms. K. Rao',
                'visitor_org': 'HCL Tech',
                'category': 'Official Visitor',
                'checkin': '2024-03-10',
                'checkout': '2024-03-12',
                'rooms': 1, 'guests': 1,
                'purpose': 'Recruitment',
                'phone': '9210987654',
                'email': 'krao@hcl.com',
                'intender_key': 'Mr. S. Kumar (Staff)',
                'bill_to': 'Guest',
                'status': BookingStatus.CHECKED_OUT,
                'remark': '',
            },
            {
                'booking_number': 'VH20240275',
                'visitor_name': 'Dr. A. Patel',
                'visitor_org': 'BITS Pilani',
                'category': 'Examiner',
                'checkin': '2024-03-08',
                'checkout': '2024-03-09',
                'rooms': 1, 'guests': 1,
                'purpose': 'Academic',
                'phone': '9109876543',
                'email': 'apatel@bits.ac.in',
                'intender_key': 'Prof. A. Jain (CSE)',
                'bill_to': 'Department',
                'status': BookingStatus.CHECKED_OUT,
                'remark': '',
            },
            {
                'booking_number': 'VH20240270',
                'visitor_name': 'Mr. S. Thakur',
                'visitor_org': 'Personal',
                'category': 'Personal Guest',
                'checkin': '2024-03-05',
                'checkout': '2024-03-06',
                'rooms': 1, 'guests': 2,
                'purpose': 'Personal',
                'phone': '9098765432',
                'email': '',
                'intender_key': 'Dr. R. Sharma (ECE)',
                'bill_to': 'Intender',
                'status': BookingStatus.CANCELLED,
                'remark': 'Change of plans',
            },
        ]

        for bd in bookings_data:
            if BookingDetail.objects.filter(booking_number=bd['booking_number']).exists():
                self.stdout.write(f"  Booking {bd['booking_number']} already exists, skipping.")
                continue

            intender_username = intender_map[bd['intender_key']]
            intender_extra = _extra(intender_username)

            # Determine if intender is faculty or staff
            intender_faculty = None
            intender_staff = None
            try:
                intender_faculty = Faculty.objects.get(id=intender_extra)
            except Faculty.DoesNotExist:
                try:
                    intender_staff = Staff.objects.get(id=intender_extra)
                except Staff.DoesNotExist:
                    pass

            checkin = datetime.date.fromisoformat(bd['checkin'])
            checkout = datetime.date.fromisoformat(bd['checkout'])

            # For checked-in/out set actual timestamps
            actual_checkin = None
            actual_checkout = None
            approved_at = None
            if bd['status'] in (BookingStatus.CHECKED_IN, BookingStatus.CHECKED_OUT, BookingStatus.CONFIRMED):
                actual_checkin = timezone.make_aware(
                    datetime.datetime.combine(checkin, datetime.time(14, 0))
                )
                approved_at = timezone.make_aware(
                    datetime.datetime.combine(checkin - datetime.timedelta(days=1), datetime.time(10, 0))
                )
            if bd['status'] == BookingStatus.CHECKED_OUT:
                actual_checkout = timezone.make_aware(
                    datetime.datetime.combine(checkout, datetime.time(11, 0))
                )

            booking = BookingDetail.objects.create(
                booking_number=bd['booking_number'],
                intender=intender_extra,
                intender_department=intender_extra.department,
                intender_faculty=intender_faculty,
                intender_staff=intender_staff,
                visitor_name=bd['visitor_name'],
                visitor_category=category_map[bd['category']],
                visitor_organization=bd['visitor_org'],
                visitor_phone=bd['phone'],
                visitor_email=bd['email'],
                check_in_date=checkin,
                check_out_date=checkout,
                number_of_guests=bd['guests'],
                number_of_rooms=bd['rooms'],
                purpose=purpose_map[bd['purpose']],
                bill_to_be_settled_by=billing_map[bd['bill_to']],
                status=bd['status'],
                remark=bd['remark'],
                caretaker=caretaker,
                actual_check_in=actual_checkin,
                actual_check_out=actual_checkout,
                approved_at=approved_at,
            )
            self.stdout.write(f"  Created booking: {booking}")

    # ── Bills ──────────────────────────────────────────────────────────────

    def _seed_bills(self):
        caretaker = _extra('nhcaretaker')
        bills_data = [
            {
                'invoice_number': 'INV20240124',
                'booking_number': 'VH20240289',
                'room_charges': 1800,
                'meal_charges': 600,
                'extra_charges': 0,
                'discount': 0,
                'total': 2400,
                'paid': 0,
                'balance': 2400,
                'payment_mode': '',
                'payment_ref': '',
                'status': BillStatus.PENDING,
                'date': '2024-03-14',
            },
            {
                'invoice_number': 'INV20240125',
                'booking_number': 'VH20240291',
                'room_charges': 4500,
                'meal_charges': 700,
                'extra_charges': 0,
                'discount': 0,
                'total': 5200,
                'paid': 5200,
                'balance': 0,
                'payment_mode': PaymentMode.CASH,
                'payment_ref': '',
                'status': BillStatus.PAID,
                'date': '2024-03-16',
            },
            {
                'invoice_number': 'INV20240120',
                'booking_number': 'VH20240280',
                'room_charges': 900,
                'meal_charges': 400,
                'extra_charges': 0,
                'discount': 0,
                'total': 1300,
                'paid': 1300,
                'balance': 0,
                'payment_mode': PaymentMode.ONLINE,
                'payment_ref': 'TXN8823',
                'status': BillStatus.LOCKED,
                'date': '2024-03-12',
            },
            {
                'invoice_number': 'INV20240118',
                'booking_number': 'VH20240275',
                'room_charges': 900,
                'meal_charges': 200,
                'extra_charges': 100,
                'discount': 0,
                'total': 1200,
                'paid': 1200,
                'balance': 0,
                'payment_mode': PaymentMode.CASH,
                'payment_ref': '',
                'status': BillStatus.LOCKED,
                'date': '2024-03-09',
            },
        ]

        for bd in bills_data:
            if Bill.objects.filter(invoice_number=bd['invoice_number']).exists():
                self.stdout.write(f"  Bill {bd['invoice_number']} already exists, skipping.")
                continue
            try:
                booking = BookingDetail.objects.get(booking_number=bd['booking_number'])
            except BookingDetail.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Booking {bd['booking_number']} not found, skipping bill {bd['invoice_number']}."
                ))
                continue

            payment_date = None
            if bd['paid'] > 0:
                payment_date = timezone.make_aware(
                    datetime.datetime.combine(
                        datetime.date.fromisoformat(bd['date']),
                        datetime.time(12, 0)
                    )
                )

            bill = Bill.objects.create(
                booking=booking,
                invoice_number=bd['invoice_number'],
                invoice_date=datetime.date.fromisoformat(bd['date']),
                room_charges=bd['room_charges'],
                meal_charges=bd['meal_charges'],
                extra_charges=bd['extra_charges'],
                discount=bd['discount'],
                total_amount=bd['total'],
                amount_paid=bd['paid'],
                balance_due=bd['balance'],
                payment_mode=bd['payment_mode'],
                payment_reference=bd['payment_ref'],
                payment_date=payment_date,
                status=bd['status'],
                generated_by=caretaker,
            )
            self.stdout.write(f"  Created bill: {bill}")

    # ── Meals ──────────────────────────────────────────────────────────────

    def _seed_meals(self):
        caretaker = _extra('nhcaretaker')
        meals_data = [
            {
                'booking_number': 'VH20240289',
                'date': '2024-03-14',
                'type': MealType.BREAKFAST,
                'persons': 1,
                'rate': 120,
                'total': 120,
                'veg': True,
            },
            {
                'booking_number': 'VH20240291',
                'date': '2024-03-14',
                'type': MealType.LUNCH,
                'persons': 2,
                'rate': 170,
                'total': 340,
                'veg': True,
            },
            {
                'booking_number': 'VH20240294',
                'date': '2024-03-14',
                'type': MealType.DINNER,
                'persons': 1,
                'rate': 180,
                'total': 180,
                'veg': False,
            },
            {
                'booking_number': 'VH20240289',
                'date': '2024-03-13',
                'type': MealType.DINNER,
                'persons': 1,
                'rate': 180,
                'total': 180,
                'veg': True,
            },
            {
                'booking_number': 'VH20240291',
                'date': '2024-03-13',
                'type': MealType.BREAKFAST,
                'persons': 2,
                'rate': 120,
                'total': 240,
                'veg': True,
            },
        ]

        for md in meals_data:
            try:
                booking = BookingDetail.objects.get(booking_number=md['booking_number'])
            except BookingDetail.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Booking {md['booking_number']} not found, skipping meal."
                ))
                continue

            meal_date = datetime.date.fromisoformat(md['date'])
            if MealBooking.objects.filter(booking=booking, meal_date=meal_date, meal_type=md['type']).exists():
                self.stdout.write(f"  Meal {md['type']} on {meal_date} for {md['booking_number']} already exists, skipping.")
                continue

            meal = MealBooking.objects.create(
                booking=booking,
                meal_date=meal_date,
                meal_type=md['type'],
                number_of_persons=md['persons'],
                vegetarian=md['veg'],
                rate_per_person=md['rate'],
                total_amount=md['total'],
                recorded_by=caretaker,
            )
            self.stdout.write(f"  Created meal: {meal}")

    # ── Inventory ──────────────────────────────────────────────────────────

    def _seed_inventory(self):
        caretaker = _extra('nhcaretaker')
        items = [
            ('Bed Sheets',     'Consumable', 4,  4,  20, 350,  'PB-2024-001', '2024-01-15'),
            ('Bath Towels',    'Consumable', 3,  3,  15, 280,  'PB-2024-002', '2024-01-20'),
            ('Pillow Covers',  'Consumable', 45, 45, 20, 120,  'PB-2024-001', '2024-01-15'),
            ('Room Soap',      'Consumable', 80, 80, 30, 35,   'PB-2024-003', '2024-02-05'),
            ('Shampoo Sachet', 'Consumable', 60, 60, 25, 25,   'PB-2024-003', '2024-02-05'),
            ('Ceiling Fan',    'Asset',      24, 22, 0,  1800, 'PB-2023-012', '2023-11-01'),
            ('TV Remote',      'Asset',      18, 16, 5,  350,  'PB-2023-015', '2023-12-10'),
            ('Water Glasses',  'Asset',      48, 44, 10, 120,  'PB-2023-011', '2023-10-15'),
            ('Hand Sanitizer', 'Consumable', 22, 22, 10, 95,   'PB-2024-004', '2024-02-20'),
            ('Room Freshener', 'Consumable', 14, 14, 8,  150,  'PB-2024-004', '2024-02-20'),
        ]

        for (name, cat, qty, usable, threshold, cost, bill_no, pur_date) in items:
            obj, created = Inventory.objects.get_or_create(
                name=name,
                defaults={
                    'category': cat,
                    'quantity': qty,
                    'usable_quantity': usable,
                    'threshold_quantity': threshold,
                    'unit_cost': cost,
                    'purchase_bill_number': bill_no,
                    'purchase_date': datetime.date.fromisoformat(pur_date),
                    'added_by': caretaker,
                }
            )
            if created:
                self.stdout.write(f"  Created inventory item: {obj}")
            else:
                self.stdout.write(f"  Inventory item '{name}' already exists, skipping.")
