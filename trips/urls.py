from django.urls import path
from .views import (
    TripListView, TripDetailView,
    TripDestinationCreateView, TripDestinationDetailView,
    ExpenseCreateView, ExpenseDetailView
)

urlpatterns = [
    path('', TripListView.as_view(), name='trip-list'),
    path('<int:trip_id>/', TripDetailView.as_view(), name='trip-detail'),

    path('destinations/add/', TripDestinationCreateView.as_view(), name='add-trip-destination'),
    path('destinations/<int:trip_destination_id>/', TripDestinationDetailView.as_view(), name='trip-destination-detail'),

    path('add-expense/', ExpenseCreateView.as_view(), name='add-expense'),
    path('expenses/<int:expense_id>/', ExpenseDetailView.as_view(), name='expense-detail'),
]