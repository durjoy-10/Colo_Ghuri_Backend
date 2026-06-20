from django.db import models
from django.db.models import Sum, Q
from destinations.models import Destination
from guides.models import GuideGroup
from users.models import User

class Tour(models.Model):
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    tour_id = models.AutoField(primary_key=True)
    tour_name = models.CharField(max_length=200)
    guide_group = models.ForeignKey(GuideGroup, on_delete=models.CASCADE, related_name='tours')
    description = models.TextField()
    total_seats = models.IntegerField(default=1)
    available_seats = models.IntegerField(default=1)
    price_per_person = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cover_image = models.ImageField(upload_to='tour_covers/', blank=True, null=True)
    total_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_locked = models.BooleanField(default=False)
    
    @property
    def final_price(self):
        """Price after discount per person"""
        return self.price_per_person * (1 - self.discount_percentage / 100)
    
    @property
    def booked_seats(self):
        """Total seats that have been booked (confirmed or completed)"""
        from .models import TourBooking
        booked = TourBooking.objects.filter(
            tour=self, 
            status__in=['confirmed', 'completed']
        ).aggregate(total=Sum('number_of_travellers'))['total'] or 0
        return booked
    
    @property
    def total_revenue(self):
        """Revenue = booked_seats * final_price per person"""
        # Calculate based on booked seats
        booked_seats_count = self.booked_seats
        revenue = booked_seats_count * self.final_price
        return revenue
    
    @property
    def net_profit(self):
        """Profit = Revenue - Expenses"""
        return self.total_revenue - self.total_expenses
    
    def release_seats(self, number_of_seats):
        """Release seats when booking is cancelled"""
        self.available_seats += number_of_seats
        self.save()
    
    def __str__(self):
        return f"{self.tour_name} - {self.guide_group.guide_groupname}"
    
    class Meta:
        db_table = 'tours'
        verbose_name_plural = 'Tours'


class TourImage(models.Model):
    image_id = models.AutoField(primary_key=True)
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='tour_images/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']
        db_table = 'tour_images'
    
    def __str__(self):
        return f"Image for {self.tour.tour_name}"


class TourDestination(models.Model):
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='destinations')
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    order = models.IntegerField()
    arrival_date = models.DateField()
    departure_date = models.DateField()
    arrival_time = models.TimeField()
    departure_time = models.TimeField()
    stay_duration_hours = models.IntegerField()
    
    class Meta:
        ordering = ['order']
        unique_together = ('tour', 'order')
        db_table = 'tour_destinations'
    
    def __str__(self):
        return f"{self.tour.tour_name} - {self.destination.name} (Day {self.order})"


class FoodPlan(models.Model):
    MEAL_TYPE = (
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
    )
    
    tour_destination = models.ForeignKey(TourDestination, on_delete=models.CASCADE, related_name='food_plans')
    day_number = models.IntegerField()
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE)
    meal_description = models.TextField()
    meal_items = models.TextField(help_text="Comma-separated meal items")
    dietary_options = models.CharField(max_length=200, blank=True)
    
    class Meta:
        unique_together = ('tour_destination', 'day_number', 'meal_type')
        db_table = 'food_plans'
    
    def __str__(self):
        return f"Day {self.day_number} - {self.meal_type} for {self.tour_destination.tour.tour_name}"


class TourBooking(models.Model):
    BOOKING_STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    )
    
    booking_id = models.AutoField(primary_key=True)
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='bookings')
    traveller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tour_bookings')
    number_of_travellers = models.IntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=100, blank=True)
    guide_reference = models.CharField(max_length=100, blank=True)
    special_requests = models.TextField(blank=True)
    
    def cancel(self):
        """Cancel booking and release seats"""
        if self.status != 'cancelled':
            self.status = 'cancelled'
            self.save()
            # Release seats
            self.tour.release_seats(self.number_of_travellers)
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.traveller.username} for {self.tour.tour_name}"
    
    class Meta:
        db_table = 'tour_bookings'
        verbose_name_plural = 'Tour Bookings'