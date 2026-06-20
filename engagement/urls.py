from django.urls import path

from .views import (
    WishlistListView,
    WishlistToggleView,
    WishlistDeleteView,
    DestinationReviewListCreateView,
    TourReviewListCreateView,
    ReviewDeleteView,
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)

urlpatterns = [
    path('wishlist/', WishlistListView.as_view(), name='wishlist-list'),
    path('wishlist/toggle/', WishlistToggleView.as_view(), name='wishlist-toggle'),
    path('wishlist/<int:item_id>/delete/', WishlistDeleteView.as_view(), name='wishlist-delete'),

    path('reviews/destinations/<int:destination_id>/', DestinationReviewListCreateView.as_view(), name='destination-reviews'),
    path('reviews/tours/<int:tour_id>/', TourReviewListCreateView.as_view(), name='tour-reviews'),
    path('reviews/<str:review_type>/<int:review_id>/delete/', ReviewDeleteView.as_view(), name='review-delete'),

    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/<int:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-read-all'),
]