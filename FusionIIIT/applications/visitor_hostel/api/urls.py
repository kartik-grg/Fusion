"""
Visitor Hostel Management System (VHMS) - API URL Configuration
"""

from django.urls import path

from .views import (
    AllBookingsView,
    BillDetailView,
    BillListView,
    BookingDetailView,
    BookingRequestView,
    CancelBookingView,
    CheckInView,
    CheckOutView,
    ConfirmBookingView,
    DashboardView,
    ExpirePendingBookingsView,
    ForwardBookingView,
    GenerateBillView,
    GuestFeedbackView,
    InventoryAddView,
    InventoryListView,
    InventoryUpdateView,
    LowStockView,
    MealBookingView,
    NotificationView,
    RejectByCaretakerView,
    RejectByInchargeView,
    ReportView,
    RoomAvailabilityView,
    RoomListView,
    SettleBillView,
)

app_name = "visitorhostel"

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────
    # GET  /api/visitorhostel/dashboard/
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # ── Room Endpoints ─────────────────────────────────────────
    # GET  /api/visitorhostel/rooms/
    path("rooms/", RoomListView.as_view(), name="room-list"),
    # GET  /api/visitorhostel/rooms/availability/?check_in_date=&check_out_date=
    path("rooms/availability/", RoomAvailabilityView.as_view(), name="room-availability"),

    # ── Booking Endpoints ──────────────────────────────────────
    # GET  /api/visitorhostel/bookings/         (intender sees own bookings)
    # POST /api/visitorhostel/bookings/         (VH-UC-001: request booking)
    path("bookings/", BookingRequestView.as_view(), name="booking-list-create"),

    # GET   /api/visitorhostel/bookings/all/    (caretaker / incharge view all)
    path("bookings/all/", AllBookingsView.as_view(), name="booking-all"),

    # GET  /api/visitorhostel/bookings/<id>/
    # PATCH /api/visitorhostel/bookings/<id>/  (VH-UC-003/UC-VH-017: modify)
    path("bookings/<int:booking_id>/", BookingDetailView.as_view(), name="booking-detail"),

    # POST /api/visitorhostel/bookings/forward/   (VH-UC-003: caretaker forwards)
    path("bookings/forward/", ForwardBookingView.as_view(), name="booking-forward"),

    # POST /api/visitorhostel/bookings/reject-caretaker/   (VH-UC-018)
    path("bookings/reject-caretaker/", RejectByCaretakerView.as_view(), name="booking-reject-caretaker"),

    # POST /api/visitorhostel/bookings/confirm/   (VH-UC-004)
    path("bookings/confirm/", ConfirmBookingView.as_view(), name="booking-confirm"),

    # POST /api/visitorhostel/bookings/reject/    (VH-UC-004: incharge rejects)
    path("bookings/reject/", RejectByInchargeView.as_view(), name="booking-reject-incharge"),

    # POST /api/visitorhostel/bookings/cancel/    (VH-UC-005/019/020)
    path("bookings/cancel/", CancelBookingView.as_view(), name="booking-cancel"),

    # POST /api/visitorhostel/bookings/check-in/   (VH-UC-007)
    path("bookings/check-in/", CheckInView.as_view(), name="booking-checkin"),

    # POST /api/visitorhostel/bookings/check-out/  (VH-UC-008)
    path("bookings/check-out/", CheckOutView.as_view(), name="booking-checkout"),

    # POST /api/visitorhostel/bookings/expire/    (VH-BR-013: admin trigger)
    path("bookings/expire/", ExpirePendingBookingsView.as_view(), name="booking-expire"),

    # ── Bill Endpoints ─────────────────────────────────────────
    # GET  /api/visitorhostel/bills/             (VH-UC-014)
    path("bills/", BillListView.as_view(), name="bill-list"),

    # GET  /api/visitorhostel/bills/<id>/
    path("bills/<int:bill_id>/", BillDetailView.as_view(), name="bill-detail"),

    # POST /api/visitorhostel/bills/generate/    (VH-UC-013)
    path("bills/generate/", GenerateBillView.as_view(), name="bill-generate"),

    # POST /api/visitorhostel/bills/settle/      (VH-UC-015)
    path("bills/settle/", SettleBillView.as_view(), name="bill-settle"),

    # ── Meal Endpoints ─────────────────────────────────────────
    # GET  /api/visitorhostel/meals/?booking_id=
    # POST /api/visitorhostel/meals/             (VH-UC-009)
    path("meals/", MealBookingView.as_view(), name="meal-booking"),

    # ── Inventory Endpoints ────────────────────────────────────
    # GET  /api/visitorhostel/inventory/          (VH-UC-012)
    path("inventory/", InventoryListView.as_view(), name="inventory-list"),

    # POST /api/visitorhostel/inventory/add/      (VH-UC-010)
    path("inventory/add/", InventoryAddView.as_view(), name="inventory-add"),

    # PATCH /api/visitorhostel/inventory/update/  (VH-UC-011)
    path("inventory/update/", InventoryUpdateView.as_view(), name="inventory-update"),

    # GET  /api/visitorhostel/inventory/low-stock/  (BR-VH-007 alert)
    path("inventory/low-stock/", LowStockView.as_view(), name="inventory-low-stock"),

    # ── Notification Endpoints ──────────────────────────────────
    # GET   /api/visitorhostel/notifications/
    # PATCH /api/visitorhostel/notifications/         (mark all read)
    path("notifications/", NotificationView.as_view(), name="notifications"),

    # PATCH /api/visitorhostel/notifications/<id>/    (mark one read)
    path("notifications/<int:notif_id>/", NotificationView.as_view(), name="notification-detail"),

    # ── Reports ─────────────────────────────────────────────────
    # GET  /api/visitorhostel/reports/?start_date=&end_date=&status=
    path("reports/", ReportView.as_view(), name="reports"),

    # ── Feedback ────────────────────────────────────────────────
    # POST /api/visitorhostel/feedback/
    path("feedback/", GuestFeedbackView.as_view(), name="guest-feedback"),
]
