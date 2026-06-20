from django.db import models
from django.db.models import Avg
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings

from destinations.models import Destination
from tours.models import Tour


class WishlistItem(models.Model):
    ITEM_TYPE_CHOICES = (
        ('destination', 'Destination'),
        ('tour', 'Tour'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name='wishlisted_by',
        null=True,
        blank=True
    )
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name='wishlisted_by',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wishlist_items'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.item_type}'


class DestinationReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='destination_reviews'
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    image = models.ImageField(upload_to='review_images/destinations/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'destination_reviews'
        ordering = ['-created_at']
        unique_together = ('user', 'destination')

    def __str__(self):
        return f'{self.destination.name} - {self.rating} stars by {self.user.username}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_destination_rating()

    def delete(self, *args, **kwargs):
        destination = self.destination
        super().delete(*args, **kwargs)
        self.update_destination_rating(destination)

    def update_destination_rating(self, destination=None):
        destination = destination or self.destination
        reviews = DestinationReview.objects.filter(destination=destination)
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

        destination.average_rating = round(avg_rating, 2)
        destination.total_reviews = reviews.count()
        destination.save(update_fields=['average_rating', 'total_reviews'])


class TourReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tour_reviews'
    )
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    image = models.ImageField(upload_to='review_images/tours/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tour_reviews'
        ordering = ['-created_at']
        unique_together = ('user', 'tour')

    def __str__(self):
        return f'{self.tour.tour_name} - {self.rating} stars by {self.user.username}'


class Notification(models.Model):
    TYPE_CHOICES = (
        ('general', 'General'),
        ('booking', 'Booking'),
        ('review', 'Review'),
        ('wishlist', 'Wishlist'),
        ('guide', 'Guide'),
        ('admin', 'Admin'),
        ('system', 'System'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.title}'