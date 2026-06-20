from django.urls import path

from .views import (
    TravellerDashboardView,
    ActivityLogListView,
    BookingTicketPDFView,
    GuideAvailabilityListCreateView,
    GuideAvailabilityDetailView,
    GuideAvailabilityCheckView,
    DestinationMapDataView,
    TourRouteMapDataView,
    ContactMessageListCreateView,
    ContactMessageDetailView,
)

urlpatterns = [
    path('traveller-dashboard/', TravellerDashboardView.as_view(), name='traveller-dashboard'),

    path('activity-logs/', ActivityLogListView.as_view(), name='activity-logs'),

    path('bookings/<int:booking_id>/ticket/', BookingTicketPDFView.as_view(), name='booking-ticket'),

    path('guide-availability/', GuideAvailabilityListCreateView.as_view(), name='guide-availability'),
    path('guide-availability/<int:id>/', GuideAvailabilityDetailView.as_view(), name='guide-availability-detail'),
    path('guide-availability/check/', GuideAvailabilityCheckView.as_view(), name='guide-availability-check'),

    path('maps/destinations/', DestinationMapDataView.as_view(), name='destination-map-data'),
    path('maps/tours/<int:tour_id>/', TourRouteMapDataView.as_view(), name='tour-route-map-data'),

    path('contact-messages/', ContactMessageListCreateView.as_view(), name='contact-messages'),
    path('contact-messages/<int:message_id>/', ContactMessageDetailView.as_view(), name='contact-message-detail'),
]