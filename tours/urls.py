from django.urls import path
from .views import (
    TourListView, TourDetailView, TourCreateView, TourUpdateView, TourDeleteView,
    TourImageUploadView, TourImageDeleteView, TourImageSetPrimaryView,
    BookingCreateView, MyBookingsView, UpdateBookingStatusView, TourCompleteView,
    TourDestinationListView, TourDestinationCreateView, TourDestinationDeleteView,
    FoodPlanCreateView, FoodPlanDeleteView
)

urlpatterns = [
    path('', TourListView.as_view(), name='tour-list'),
    path('create/', TourCreateView.as_view(), name='tour-create'),
    path('<int:tour_id>/', TourDetailView.as_view(), name='tour-detail'),
    path('<int:tour_id>/update/', TourUpdateView.as_view(), name='tour-update'),
    path('<int:tour_id>/delete/', TourDeleteView.as_view(), name='tour-delete'),
    path('<int:tour_id>/complete/', TourCompleteView.as_view(), name='tour-complete'),
    path('<int:tour_id>/destinations/', TourDestinationListView.as_view(), name='tour-destinations'),
    path('<int:tour_id>/destinations/create/', TourDestinationCreateView.as_view(), name='tour-destination-create'),
    path('destinations/<int:id>/delete/', TourDestinationDeleteView.as_view(), name='tour-destination-delete'),
    path('destinations/<int:tour_destination_id>/food-plans/create/', FoodPlanCreateView.as_view(), name='food-plan-create'),
    path('food-plans/<int:id>/delete/', FoodPlanDeleteView.as_view(), name='food-plan-delete'),
    path('upload-image/', TourImageUploadView.as_view(), name='tour-upload-image'),
    path('delete-image/<int:image_id>/', TourImageDeleteView.as_view(), name='tour-delete-image'),
    path('images/<int:image_id>/set-primary/', TourImageSetPrimaryView.as_view(), name='tour-image-set-primary'),
    path('update-booking/<int:booking_id>/', UpdateBookingStatusView.as_view(), name='update-booking'),
    path('book/', BookingCreateView.as_view(), name='booking-create'),
    path('my-bookings/', MyBookingsView.as_view(), name='my-bookings'),
]