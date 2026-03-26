"""
Visitor Hostel Management System (VHMS) - API Views (thin views only)
All business logic is delegated to services.py
"""

from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.globals.models import ExtraInfo, HoldsDesignation

from ..models import (
    Bill, BookingDetail, GuestFeedback, Inventory, MealBooking,
    Notification, RoomDetail,
)
from ..selectors import (
    get_all_bills, get_all_bookings, get_all_inventory,
    get_all_notifications, get_available_rooms, get_bill_by_id,
    get_booking_by_id, get_bookings_by_intender, get_checked_in_bookings,
    get_dashboard_stats, get_forwarded_bookings, get_inventory_by_id,
    get_low_stock_items, get_meals_for_booking, get_pending_bookings,
    get_unread_notifications,
    get_room_by_id, get_all_rooms,
)
from ..services import (
    VHError, add_inventory_item, approve_booking_cancellation_request,
    check_in, check_out, check_room_availability,
    compute_cancellation_charges, confirm_booking, create_booking,
    expire_pending_bookings, forward_booking, generate_bill,
    generate_booking_report, mark_no_show, modify_booking, record_meal,
    reject_booking_by_caretaker, reject_booking_by_incharge,
    request_booking_cancellation, settle_bill, update_inventory_item,
)
from .serializers import (
    ApproveCancellationSerializer, BillSerializer,
    BookingCreateSerializer, BookingDetailSerializer,
    BookingListSerializer, BookingModifySerializer, BuildingSerializer,
    CancellationPreviewSerializer,
    CancelBookingSerializer, CheckInSerializer, CheckOutSerializer,
    ConfirmBookingSerializer, ForwardBookingSerializer, GuestFeedbackSerializer,
    InventorySerializer, InventoryUpdateSerializer, MealBookingSerializer,
    NoShowSerializer, NotificationSerializer, RejectBookingSerializer, RoomAvailabilitySerializer,
    RoomDetailSerializer, SettleBillSerializer,
)


def _get_extrainfo(request):
    """Helper: get ExtraInfo for authenticated user."""
    return get_object_or_404(ExtraInfo, user=request.user)


def _normalize_role(role_value: str) -> str:
    return (
        str(role_value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def _matches_vh_staff_role(role_value: str) -> bool:
    """Best-effort matcher for Visitor Hostel caretaker/incharge role strings."""
    role = _normalize_role(role_value)
    if not role:
        return False

    known_exact = {
        "vhcaretaker",
        "visitorhostelcaretaker",
        "hostelcaretaker",
        "caretaker",
        "vhincharge",
        "visitorhostelincharge",
        "hostelincharge",
        "incharge",
    }
    if role in known_exact:
        return True

    has_scope = any(token in role for token in ["visitorhostel", "guesthouse", "vh"])
    has_position = any(token in role for token in ["caretaker", "incharge"])
    return has_scope and has_position


def _is_vh_staff(extrainfo: ExtraInfo) -> bool:
    """Return True when user is acting as Visitor Hostel caretaker/incharge."""
    if _matches_vh_staff_role(extrainfo.last_selected_role):
        return True

    # Fallback: detect from Django groups if active role is not persisted.
    group_names = extrainfo.user.groups.values_list("name", flat=True)
    if any(_matches_vh_staff_role(name) for name in group_names):
        return True

    # Fallback: detect from holds-designation naming conventions.
    designation_names = HoldsDesignation.objects.filter(
        working=extrainfo.user,
    ).values_list("designation__name", "designation__full_name")
    return any(
        _matches_vh_staff_role(name) or _matches_vh_staff_role(full_name)
        for name, full_name in designation_names
    )


def _is_vh_caretaker(extrainfo: ExtraInfo) -> bool:
    role = _normalize_role(extrainfo.last_selected_role)
    if role and "caretaker" in role:
        return True

    group_names = extrainfo.user.groups.values_list("name", flat=True)
    if any("caretaker" in _normalize_role(name) for name in group_names):
        return True

    designation_names = HoldsDesignation.objects.filter(
        working=extrainfo.user,
    ).values_list("designation__name", "designation__full_name")
    return any(
        "caretaker" in _normalize_role(name) or "caretaker" in _normalize_role(full_name)
        for name, full_name in designation_names
    )


# ──────────────────────────── Dashboard (VH-UC-016) ────────────────────────────

class DashboardView(APIView):
    """VH-UC-016: View dashboard overview — VH-BR-011: Authentication required."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_dashboard_stats())


# ──────────────────────────── Room Views ────────────────────────────

class RoomListView(APIView):
    """List all rooms with optional filters."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        room_type = request.query_params.get("room_type")
        building_id = request.query_params.get("building_id")
        rooms = get_all_rooms(room_type, building_id)
        return Response(RoomDetailSerializer(rooms, many=True).data)


class RoomAvailabilityView(APIView):
    """VH-UC-006 / VH-WF-007: Check room availability — VH-BR-012."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = RoomAvailabilitySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            rooms = check_room_availability(
                check_in=data["check_in_date"],
                check_out=data["check_out_date"],
                room_type=data.get("room_type") or None,
                building_id=data.get("building_id"),
            )
            return Response(RoomDetailSerializer(rooms, many=True).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────── Booking Views ────────────────────────────

class BookingRequestView(APIView):
    """
    VH-UC-001: request_booking (POST)
    VH-UC-002: view_booking_requests for intender (GET)
    VH-BR-010: Authorize intender actions
    VH-BR-011: Authentication required
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        extrainfo = _get_extrainfo(request)
        bookings = get_bookings_by_intender(extrainfo.id)
        return Response(BookingListSerializer(bookings, many=True).data)

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        extrainfo = _get_extrainfo(request)
        d = serializer.validated_data
        # Auto-detect if caretaker is creating booking and mark as offline
        is_offline = d.get("is_offline", False)
        if _is_vh_caretaker(extrainfo):
            is_offline = True
            
        try:
            booking = create_booking(
                intender_extrainfo=extrainfo,
                visitor_name=d["visitor_name"],
                visitor_category=d["visitor_category"],
                visitor_phone=d["visitor_phone"],
                check_in_date=d["check_in_date"],
                check_out_date=d["check_out_date"],
                number_of_guests=d["number_of_guests"],
                number_of_rooms=d["number_of_rooms"],
                purpose=d["purpose"],
                bill_to_be_settled_by=d["bill_to_be_settled_by"],
                preferred_room_type=d.get("preferred_room_type", ""),
                purpose_details=d.get("purpose_details", ""),
                visitor_email=d.get("visitor_email", ""),
                visitor_organization=d.get("visitor_organization", ""),
                visitor_designation=d.get("visitor_designation", ""),
                visitor_address=d.get("visitor_address", ""),
                id_proof_type=d.get("id_proof_type", ""),
                id_proof_number=d.get("id_proof_number", ""),
                project_number=d.get("project_number", ""),
                remark=d.get("remark", ""),
                is_offline=is_offline,
            )
            return Response(
                BookingDetailSerializer(booking).data,
                status=status.HTTP_201_CREATED,
            )
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CaretakerBookingCreateView(APIView):
    """VH-UC-001 (CARETAKER): Create offline booking on behalf of intender.
    VH-BR-010: Authorize caretaker actions
    VH-BR-011: Authentication required
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        caretaker_extrainfo = _get_extrainfo(request)
        # Verify caretaker role
        if not _is_vh_caretaker(caretaker_extrainfo):
            return Response(
                {"error": "Only VH caretakers can create offline bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        
        # Get the intender from request data
        intender_extrainfo_id = request.data.get("intender_id")
        if not intender_extrainfo_id:
            return Response(
                {"error": "intender_id is required for caretaker booking creation."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            intender_extrainfo = ExtraInfo.objects.get(id=intender_extrainfo_id)
        except ExtraInfo.DoesNotExist:
            return Response(
                {"error": "Specified intender not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        try:
            booking = create_booking(
                intender_extrainfo=intender_extrainfo,
                visitor_name=d["visitor_name"],
                visitor_category=d["visitor_category"],
                visitor_phone=d["visitor_phone"],
                check_in_date=d["check_in_date"],
                check_out_date=d["check_out_date"],
                number_of_guests=d["number_of_guests"],
                number_of_rooms=d["number_of_rooms"],
                purpose=d["purpose"],
                bill_to_be_settled_by=d["bill_to_be_settled_by"],
                preferred_room_type=d.get("preferred_room_type", ""),
                purpose_details=d.get("purpose_details", ""),
                visitor_email=d.get("visitor_email", ""),
                visitor_organization=d.get("visitor_organization", ""),
                visitor_designation=d.get("visitor_designation", ""),
                visitor_address=d.get("visitor_address", ""),
                id_proof_type=d.get("id_proof_type", ""),
                id_proof_number=d.get("id_proof_number", ""),
                project_number=d.get("project_number", ""),
                remark=d.get("remark", ""),
                is_offline=True,  # Always mark as offline when created by caretaker
                caretaker=caretaker_extrainfo,
            )
            return Response(
                BookingDetailSerializer(booking).data,
                status=status.HTTP_201_CREATED,
            )
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BookingDetailView(APIView):
    """Retrieve / modify a specific booking."""
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        booking = get_object_or_404(BookingDetail, pk=booking_id)
        extrainfo = _get_extrainfo(request)
        if booking.intender_id != extrainfo.id and not _is_vh_staff(extrainfo):
            return Response(
                {"error": "You are not allowed to view this booking."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(BookingDetailSerializer(booking).data)

    def patch(self, request, booking_id):
        """UC-VH-017 / VH-UC-003: Modify Booking — VH-BR-021."""
        booking = get_object_or_404(BookingDetail, pk=booking_id)
        serializer = BookingModifySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        extrainfo = _get_extrainfo(request)
        try:
            updated = modify_booking(booking, extrainfo, **serializer.validated_data)
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AllBookingsView(APIView):
    """
    VH-UC-002: view_booking_requests for caretaker / incharge.
    VH-BR-008: Caretaker authorization
    VH-BR-009: Incharge authorization
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get("status")
        bookings = get_all_bookings(status_filter)
        return Response(BookingListSerializer(bookings, many=True).data)


class ForwardBookingView(APIView):
    """VH-UC-003: Forward booking to VH Incharge — VH-BR-008."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ForwardBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(BookingDetail, pk=serializer.validated_data["booking_id"])
        caretaker = _get_extrainfo(request)
        try:
            updated = forward_booking(booking, caretaker)
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RejectByCaretakerView(APIView):
    """VH-UC-018: Caretaker rejects booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RejectBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        caretaker = _get_extrainfo(request)
        try:
            updated = reject_booking_by_caretaker(booking, caretaker, d["reason"])
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ConfirmBookingView(APIView):
    """VH-UC-004: Confirm booking — VH-BR-009 / VH-BR-022."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        incharge = _get_extrainfo(request)
        try:
            updated = confirm_booking(booking, incharge, d["room_ids"], d.get("remarks", ""))
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RejectByInchargeView(APIView):
    """VH-UC-004: Incharge rejects booking — VH-BR-009."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RejectBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        incharge = _get_extrainfo(request)
        try:
            updated = reject_booking_by_incharge(booking, incharge, d["reason"])
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancelBookingView(APIView):
    """Intender submits cancellation request after reviewing charges."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CancelBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        actor = _get_extrainfo(request)
        try:
            updated = request_booking_cancellation(booking, actor, d.get("reason", ""))
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancellationPreviewView(APIView):
    """Preview BR-VH-005 cancellation charges before creating request."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CancellationPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(BookingDetail, pk=serializer.validated_data["booking_id"])
        actor = _get_extrainfo(request)
        if booking.intender_id != actor.id:
            return Response({"error": "Only the booking intender can preview cancellation charges."}, status=status.HTTP_403_FORBIDDEN)
        try:
            details = compute_cancellation_charges(booking)
            return Response(details)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ApproveCancellationView(APIView):
    """Caretaker approves cancellation request and finalizes booking cancellation."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ApproveCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(BookingDetail, pk=serializer.validated_data["booking_id"])
        actor = _get_extrainfo(request)
        if not _is_vh_caretaker(actor):
            return Response({"error": "Only caretaker can approve cancellation requests."}, status=status.HTTP_403_FORBIDDEN)
        try:
            updated = approve_booking_cancellation_request(booking, actor)
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CheckInView(APIView):
    """VH-UC-007: Check in — VH-BR-008 / VH-BR-017."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        caretaker = _get_extrainfo(request)
        try:
            updated = check_in(booking, caretaker, d.get("visitor_details", []))
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NoShowView(APIView):
    """VH-UC-007 Alternate Flow A1: caretaker marks a confirmed booking as no-show."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = NoShowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(BookingDetail, pk=serializer.validated_data["booking_id"])
        caretaker = _get_extrainfo(request)
        if not _is_vh_caretaker(caretaker):
            return Response({"error": "Only caretaker can mark no-show."}, status=status.HTTP_403_FORBIDDEN)
        try:
            updated = mark_no_show(booking, caretaker)
            return Response(BookingDetailSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CheckOutView(APIView):
    """VH-UC-008: Check-out + billing with overstay handling — VH-BR-001/002/003/018."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        booking = get_object_or_404(BookingDetail, pk=d["booking_id"])
        caretaker = _get_extrainfo(request)
        try:
            bill = check_out(
                booking=booking,
                caretaker=caretaker,
                extra_charges=d.get("extra_charges", Decimal("0")),
                overstay_hours=d.get("overstay_hours", 0),
                overstay_charges=d.get("overstay_charges", Decimal("0")),
                discount=d.get("discount", Decimal("0")),
                inventory_usage=d.get("inventory_usage", []),
            )
            return Response(BillSerializer(bill).data, status=status.HTTP_201_CREATED)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────── Bill Views ────────────────────────────

class BillListView(APIView):
    """VH-UC-014: View bills — VH-BR-011."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get("status")
        extrainfo = _get_extrainfo(request)

        if _is_vh_staff(extrainfo):
            bills = get_all_bills(status_filter)
        else:
            bills = Bill.objects.select_related("booking__intender__user").filter(
                booking__intender=extrainfo,
            ).order_by("-created_at")
            if status_filter:
                bills = bills.filter(status=status_filter)

        return Response(BillSerializer(bills, many=True).data)


class BillDetailView(APIView):
    """Get a specific bill."""
    permission_classes = [IsAuthenticated]

    def get(self, request, bill_id):
        bill = get_object_or_404(Bill, pk=bill_id)
        return Response(BillSerializer(bill).data)


class GenerateBillView(APIView):
    """VH-UC-013: Generate bill — VH-BR-028."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get("booking_id")
        if not booking_id:
            return Response({"error": "booking_id required."}, status=status.HTTP_400_BAD_REQUEST)
        booking = get_object_or_404(BookingDetail, pk=booking_id)
        actor = _get_extrainfo(request)
        try:
            bill = generate_bill(booking, actor)
            return Response(BillSerializer(bill).data, status=status.HTTP_201_CREATED)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SettleBillView(APIView):
    """VH-UC-015: Settle bill — VH-BR-040."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SettleBillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        bill = get_object_or_404(Bill, pk=d["bill_id"])
        actor = _get_extrainfo(request)
        if not _is_vh_caretaker(actor):
            return Response({"error": "Only caretaker can settle bills."}, status=status.HTTP_403_FORBIDDEN)
        try:
            updated = settle_bill(
                bill=bill,
                amount=d["amount"],
                payment_mode=d["payment_mode"],
                received_by=actor,
                reference_number=d.get("reference_number", ""),
                remarks=d.get("remarks", ""),
            )
            return Response(BillSerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────── Meal Views ────────────────────────────

class MealBookingView(APIView):
    """VH-UC-009: Record meal — BR-VH-011."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        booking_id = request.query_params.get("booking_id")
        if not booking_id:
            return Response({"error": "booking_id param required."}, status=status.HTTP_400_BAD_REQUEST)
        meals = get_meals_for_booking(booking_id)
        return Response(MealBookingSerializer(meals, many=True).data)

    def post(self, request):
        serializer = MealBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        caretaker = _get_extrainfo(request)
        try:
            meal = record_meal(
                booking=d["booking"],
                meal_date=d["meal_date"],
                meal_type=d["meal_type"],
                number_of_persons=d["number_of_persons"],
                rate_per_person=d["rate_per_person"],
                recorded_by=caretaker,
                vegetarian=d.get("vegetarian", True),
                special_requirements=d.get("special_requirements", ""),
            )
            return Response(MealBookingSerializer(meal).data, status=status.HTTP_201_CREATED)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────── Inventory Views ────────────────────────────

class InventoryListView(APIView):
    """VH-UC-012: View inventory — VH-BR-011."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        category = request.query_params.get("category")
        items = get_all_inventory(category)
        return Response(InventorySerializer(items, many=True).data)


class InventoryAddView(APIView):
    """VH-UC-010: Add inventory item — VH-BR-029 / VH-BR-035."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        actor = _get_extrainfo(request)
        try:
            item = add_inventory_item(
                name=d["name"],
                category=d["category"],
                quantity=d["quantity"],
                unit=d["unit"],
                added_by=actor,
                purchase_bill_number=d.get("purchase_bill_number", ""),
                unit_cost=d.get("unit_cost", Decimal("0")),
                threshold_quantity=d.get("threshold_quantity", 5),
                description=d.get("description", ""),
                usable_quantity=d.get("usable_quantity"),
                purchase_date=d.get("purchase_date"),
            )
            return Response(InventorySerializer(item).data, status=status.HTTP_201_CREATED)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InventoryUpdateView(APIView):
    """VH-UC-011: Update inventory — VH-BR-019 / VH-BR-020."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = InventoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        item = get_object_or_404(Inventory, pk=d["item_id"])
        actor = _get_extrainfo(request)
        try:
            updated = update_inventory_item(item, d["quantity_delta"], actor)
            if updated is None:
                return Response(
                    {"message": "Inventory item deleted (quantity reached zero)."},
                    status=status.HTTP_200_OK,
                )
            return Response(InventorySerializer(updated).data)
        except VHError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LowStockView(APIView):
    """BR-VH-007: Low stock items alert."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = get_low_stock_items()
        return Response(InventorySerializer(items, many=True).data)


# ──────────────────────────── Notification Views ────────────────────────────

class NotificationView(APIView):
    """VH-BR-014: Notifications."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = request.query_params.get("unread", "false").lower() == "true"
        if unread_only:
            notifs = get_unread_notifications(request.user.pk)
        else:
            notifs = get_all_notifications(request.user.pk)
        return Response(NotificationSerializer(notifs, many=True).data)

    def patch(self, request, notif_id=None):
        """Mark notification as read."""
        if notif_id:
            notif = get_object_or_404(Notification, pk=notif_id, recipient=request.user)
            notif.is_read = True
            notif.save()
            return Response({"message": "Marked as read."})
        # Mark all as read
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All notifications marked as read."})


# ──────────────────────────── Reports (VH-UC-021) ────────────────────────────

class ReportView(APIView):
    """VH-UC-021 / WF-VH-009: Generate reports — VH-BR-009."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import date as dt
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        booking_status = request.query_params.get("status")
        if not start or not end:
            return Response(
                {"error": "start_date and end_date are required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start_date = dt.fromisoformat(start)
            end_date = dt.fromisoformat(end)
        except ValueError:
            return Response({"error": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)

        report = generate_booking_report(start_date, end_date, booking_status)
        report["bookings"] = BookingListSerializer(report["bookings"], many=True).data
        return Response(report)


# ──────────────────────────── Feedback ────────────────────────────

class GuestFeedbackView(APIView):
    """Guest feedback after checkout."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GuestFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.validated_data["booking"]
        feedback, created = GuestFeedback.objects.get_or_create(
            booking=booking,
            defaults=serializer.validated_data,
        )
        if not created:
            return Response(
                {"error": "Feedback already submitted for this booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(GuestFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


# ──────────────────────────── Expire Pending Bookings (Scheduled) ────────────────────────────

class ExpirePendingBookingsView(APIView):
    """VH-BR-013: Trigger expiry of outdated pending bookings. For admin/cron use."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = expire_pending_bookings()
        return Response({"expired_count": count})
