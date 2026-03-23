"""
Visitor Hostel Management System (VHMS) - Models
Implements: VH-UC-001 to VH-UC-021, VH-BR-001 to VH-BR-042
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from applications.globals.models import ExtraInfo, DepartmentInfo, Faculty, Staff, Designation, HoldsDesignation
from applications.programme_curriculum.models import Discipline


# ──────────────────────────── CHOICES (TextChoices / IntegerChoices) ────────────────────────────

class BookingStatus(models.TextChoices):
    """VH-BR-005: Enforce Booking Status Lifecycle"""
    PENDING = "Pending", "Pending"
    FORWARDED = "Forwarded", "Forwarded"
    CONFIRMED = "Confirmed", "Confirmed"
    CHECKED_IN = "CheckedIn", "Checked In"
    CHECKED_OUT = "CheckedOut", "Checked Out"
    CANCELLED = "Cancelled", "Cancelled"
    REJECTED = "Rejected", "Rejected"
    EXPIRED = "Expired", "Expired"


class RoomStatus(models.TextChoices):
    """VH-BR-006: Enforce Room Status Lifecycle"""
    AVAILABLE = "Available", "Available"
    OCCUPIED = "Occupied", "Occupied"
    MAINTENANCE = "Maintenance", "Under Maintenance"
    BLOCKED = "Blocked", "Blocked"


class RoomType(models.TextChoices):
    """VH-BR-031: Restrict Room Type Values"""
    SINGLE = "Single", "Single"
    DOUBLE = "Double", "Double"
    SUITE = "Suite", "Suite"
    DORMITORY = "Dormitory", "Dormitory"


class RoomFloor(models.IntegerChoices):
    """VH-BR-032: Restrict Room Floor Values"""
    GROUND = 0, "Ground Floor"
    FIRST = 1, "First Floor"
    SECOND = 2, "Second Floor"
    THIRD = 3, "Third Floor"
    FOURTH = 4, "Fourth Floor"


class VisitorCategory(models.TextChoices):
    """VH-BR-030: Restrict Visitor Category Values"""
    IIIT_FACULTY = "IIIT_Faculty", "IIIT Faculty"
    IIIT_STAFF = "IIIT_Staff", "IIIT Staff"
    IIIT_STUDENT = "IIIT_Student", "IIIT Student"
    GUEST_SPEAKER = "Guest_Speaker", "Guest Speaker"
    EXAMINER = "Examiner", "External Examiner"
    OFFICIAL = "Official", "Official Visitor"
    PERSONAL = "Personal", "Personal Guest"
    OTHER = "Other", "Other"


class PurposeType(models.TextChoices):
    ACADEMIC = "Academic", "Academic"
    CONFERENCE = "Conference", "Conference / Seminar"
    OFFICIAL = "Official", "Official Work"
    RECRUITMENT = "Recruitment", "Recruitment"
    PERSONAL = "Personal", "Personal"
    OTHER = "Other", "Other"


class BillSettledBy(models.TextChoices):
    """VH-BR-004: Assign Bill Settlement Party"""
    INTENDER = "Intender", "Intender"
    DEPARTMENT = "Department", "Department"
    PROJECT = "Project", "Project Account"
    GUEST = "Guest", "Guest (Self)"
    INSTITUTE = "Institute", "Institute"


class BillStatus(models.TextChoices):
    """VH-BR-040: Billing Finality Rule"""
    GENERATED = "Generated", "Generated"
    PENDING = "Pending", "Payment Pending"
    PAID = "Paid", "Paid"
    CANCELLED = "Cancelled", "Cancelled"
    LOCKED = "Locked", "Locked"


class PaymentMode(models.TextChoices):
    CASH = "Cash", "Cash"
    CHEQUE = "Cheque", "Cheque"
    ONLINE = "Online", "Online Transfer"
    DD = "DD", "Demand Draft"


class MealType(models.TextChoices):
    BREAKFAST = "Breakfast", "Breakfast"
    LUNCH = "Lunch", "Lunch"
    DINNER = "Dinner", "Dinner"
    HIGH_TEA = "High_Tea", "High Tea"


class InventoryCategory(models.TextChoices):
    """VH-BR-029: Classify Inventory as Consumable or Asset"""
    CONSUMABLE = "Consumable", "Consumable"
    ASSET = "Asset", "Asset / Reusable"


# ──────────────────────────── ROOM MANAGEMENT ────────────────────────────

class Building(models.Model):
    """Guest house buildings"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=200, blank=True)
    total_rooms = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RoomDetail(models.Model):
    """
    Individual room details.
    VH-BR-027: Enforce Unique Room Numbers
    VH-BR-031: Restrict Room Type Values
    VH-BR-032: Restrict Room Floor Values
    VH-BR-006: Room Status Lifecycle
    """
    building = models.ForeignKey('visitor_hostel.Building', on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=20)
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    floor = models.IntegerField(choices=RoomFloor.choices, default=RoomFloor.GROUND)
    bed_count = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_occupancy = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    has_ac = models.BooleanField(default=False)
    has_attached_bathroom = models.BooleanField(default=True)
    amenities = models.TextField(blank=True, help_text="Comma-separated list of amenities")
    status = models.CharField(max_length=20, choices=RoomStatus.choices, default=RoomStatus.AVAILABLE)
    # Tariff
    tariff_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tariff_faculty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tariff_staff = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tariff_student = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tariff_external = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ["building", "room_number"]  # VH-BR-027
        ordering = ["building", "room_number"]

    def __str__(self):
        return f"{self.building.code}-{self.room_number} ({self.room_type})"


# ──────────────────────────── BOOKING ────────────────────────────

class BookingDetail(models.Model):
    """
    Core booking model.
    VH-BR-005: Booking Status Lifecycle
    VH-BR-023: Validate Booking Date Consistency
    VH-BR-033: Auto-Assign Booking Creation Timestamp
    VH-BR-034: Limit Booking Remark Length
    VH-BR-026: Assign Default Caretaker
    VH-BR-004: Bill Settlement Party
    """
    booking_number = models.CharField(max_length=50, unique=True)  # auto-generated

    # Who is booking (Intender)
    intender = models.ForeignKey(
        ExtraInfo, on_delete=models.CASCADE, related_name="vh_bookings"
    )
    intender_department = models.ForeignKey(
        DepartmentInfo, on_delete=models.SET_NULL, null=True, blank=True
    )
    intender_faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name="vh_faculty_bookings"
    )
    intender_staff = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="vh_staff_bookings"
    )
    discipline = models.ForeignKey(
        Discipline, on_delete=models.SET_NULL, null=True, blank=True, related_name="vh_discipline_bookings"
    )

    # Visitor details
    visitor_name = models.CharField(max_length=200)
    visitor_category = models.CharField(
        max_length=30, choices=VisitorCategory.choices
    )  # VH-BR-030
    visitor_organization = models.CharField(max_length=200, blank=True)
    visitor_designation = models.CharField(max_length=100, blank=True)
    visitor_phone = models.CharField(max_length=15)
    visitor_email = models.EmailField(blank=True)
    visitor_address = models.TextField(blank=True)
    id_proof_type = models.CharField(max_length=50, blank=True)
    id_proof_number = models.CharField(max_length=50, blank=True)

    # Stay details
    check_in_date = models.DateField()   # VH-BR-023, VH-BR-041
    check_out_date = models.DateField()  # VH-BR-023, VH-BR-041
    number_of_guests = models.IntegerField(
        default=1, validators=[MinValueValidator(1)]
    )  # VH-BR-024
    number_of_rooms = models.IntegerField(
        default=1, validators=[MinValueValidator(1)]
    )  # VH-BR-024
    preferred_room_type = models.CharField(
        max_length=20, choices=RoomType.choices, blank=True
    )

    # Purpose
    purpose = models.CharField(max_length=20, choices=PurposeType.choices)
    purpose_details = models.TextField(blank=True)

    # Billing responsibility
    bill_to_be_settled_by = models.CharField(
        max_length=20, choices=BillSettledBy.choices, default=BillSettledBy.INTENDER
    )  # VH-BR-004
    project_number = models.CharField(max_length=50, blank=True)

    # Booking metadata
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING
    )  # VH-BR-005, VH-BR-038
    booking_date = models.DateTimeField(auto_now_add=True)  # VH-BR-033
    remark = models.CharField(max_length=500, blank=True)  # VH-BR-034

    # Caretaker assigned
    caretaker = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="caretaker_bookings"
    )  # VH-BR-026

    # Approval
    forwarded_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="forwarded_bookings"
    )
    forwarded_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_bookings"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_designation = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name="vh_approval_designation"
    )
    approval_holder = models.ForeignKey(
        HoldsDesignation, on_delete=models.SET_NULL, null=True, blank=True, related_name="vh_approval_holder"
    )
    rejection_reason = models.TextField(blank=True)

    # Actual check-in/out timestamps
    actual_check_in = models.DateTimeField(null=True, blank=True)
    actual_check_out = models.DateTimeField(null=True, blank=True)

    # Is offline booking
    is_offline = models.BooleanField(default=False)  # VH-BR-003 / BR-VH-017

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-booking_date"]

    def __str__(self):
        return f"{self.booking_number} – {self.visitor_name} ({self.status})"


class VisitorDetail(models.Model):
    """
    Actual visitor details recorded at check-in.
    VH-BR-017: Accept Actual Visitor Details at Check-In
    VH-BR-025: Validate Minimum Visitor Details
    """
    booking = models.ForeignKey(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="visitor_details"
    )
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    id_proof_type = models.CharField(max_length=50, blank=True)
    id_proof_number = models.CharField(max_length=50, blank=True)
    relationship_to_intender = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.booking.booking_number})"


class RoomAllocation(models.Model):
    """
    Links confirmed bookings to specific rooms.
    VH-BR-022: Assign Rooms During Confirmation
    VH-BR-012: Room Availability Calculation
    """
    booking = models.ForeignKey(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="room_allocations"
    )
    room = models.ForeignKey('visitor_hostel.RoomDetail', on_delete=models.PROTECT, related_name="allocations")
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="room_allocations_done"
    )

    class Meta:
        ordering = ["-allocated_at"]

    def __str__(self):
        return f"{self.room} → {self.booking.booking_number}"


# ──────────────────────────── BILLING ────────────────────────────

class Bill(models.Model):
    """
    One bill per booking.
    VH-BR-001: Calculate Room Bill by Visitor Category
    VH-BR-002: Calculate Meal Bill
    VH-BR-003: Calculate Total Bill Amount
    VH-BR-028: One-to-One Booking-Bill Relationship
    VH-BR-040: Billing Finality Rule (status locked after completion)
    """
    booking = models.OneToOneField(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="bill"
    )  # VH-BR-028
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField()

    # Amounts
    room_charges = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )  # VH-BR-001
    meal_charges = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )  # VH-BR-002
    extra_charges = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )  # VH-BR-003

    # Payment
    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_mode = models.CharField(
        max_length=20, choices=PaymentMode.choices, blank=True
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=BillStatus.choices, default=BillStatus.GENERATED
    )  # VH-BR-040

    # Billing to
    billed_to_name = models.CharField(max_length=200, blank=True)
    billed_to_address = models.TextField(blank=True)

    generated_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="generated_bills"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bill {self.invoice_number} for {self.booking.booking_number}"


class Payment(models.Model):
    """Offline payment records — VH-BR-006"""
    bill = models.ForeignKey('visitor_hostel.Bill', on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_date = models.DateTimeField()
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices)
    reference_number = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="received_payments"
    )
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"₹{self.amount} for {self.bill.invoice_number}"


# ──────────────────────────── MEAL BOOKINGS ────────────────────────────

class MealBooking(models.Model):
    """
    Meal bookings during stay.
    VH-BR-002: Calculate Meal Bill from Meal Records
    BR-VH-011: Meal Booking Deadline (enforced in service layer)
    """
    booking = models.ForeignKey(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="meal_bookings"
    )
    meal_date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    number_of_persons = models.IntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    vegetarian = models.BooleanField(default=True)
    special_requirements = models.TextField(blank=True)
    rate_per_person = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    recorded_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="recorded_meals"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["booking", "meal_date", "meal_type"]
        ordering = ["meal_date", "meal_type"]

    def __str__(self):
        return f"{self.meal_type} on {self.meal_date} for {self.booking.booking_number}"


# ──────────────────────────── INVENTORY ────────────────────────────

class Inventory(models.Model):
    """
    Hostel inventory tracking.
    VH-BR-019: Calculate Total Inventory Stock
    VH-BR-020: Delete Inventory Item When Quantity Zero
    VH-BR-029: Classify Inventory as Consumable or Asset
    VH-BR-035: Track Inventory Purchase Bill Number
    VH-BR-024: Enforce Positive Quantities
    """
    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=20, choices=InventoryCategory.choices, default=InventoryCategory.CONSUMABLE
    )  # VH-BR-029
    description = models.TextField(blank=True)
    quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )  # VH-BR-024
    usable_quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )  # VH-BR-019
    unit = models.CharField(max_length=30, default="piece")
    purchase_bill_number = models.CharField(max_length=100, blank=True)  # VH-BR-035
    purchase_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    threshold_quantity = models.IntegerField(default=5)
    added_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="inventory_added"
    )
    updated_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_updated"
    )
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"


class InventoryUsage(models.Model):
    """
    Track consumable inventory usage per checkout.
    VH-BR-018: Update Consumable Inventory on Check-Out
    """
    booking = models.ForeignKey(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="inventory_usages"
    )
    inventory_item = models.ForeignKey(
        'visitor_hostel.Inventory', on_delete=models.CASCADE, related_name="usages"
    )
    quantity_used = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        ExtraInfo, on_delete=models.SET_NULL, null=True, related_name="inventory_usages_recorded"
    )

    def __str__(self):
        return f"{self.inventory_item.name} x{self.quantity_used} ({self.booking.booking_number})"


# ──────────────────────────── NOTIFICATIONS ────────────────────────────

class Notification(models.Model):
    """
    VH-BR-014: Send Notification on Booking Status Change
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vh_notifications")
    booking = models.ForeignKey(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, null=True, blank=True,
        related_name="notifications"
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notif to {self.recipient.username}: {self.subject}"


# ──────────────────────────── FEEDBACK ────────────────────────────

class GuestFeedback(models.Model):
    """Guest feedback after checkout"""
    booking = models.OneToOneField(
        'visitor_hostel.BookingDetail', on_delete=models.CASCADE, related_name="feedback"
    )
    room_cleanliness = models.IntegerField(null=True, blank=True)
    room_amenities = models.IntegerField(null=True, blank=True)
    staff_behavior = models.IntegerField(null=True, blank=True)
    food_quality = models.IntegerField(null=True, blank=True)
    overall_experience = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    suggestions = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.booking.booking_number}"
