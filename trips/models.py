from django.db import models
from users.models import User
from destinations.models import Destination

class Trip(models.Model):
    TRIP_STATUS = (
        ('planning', 'Planning'),
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    trip_id = models.AutoField(primary_key=True)
    traveller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
    trip_name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    total_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=TRIP_STATUS, default='planning')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.trip_name} - {self.traveller.username}"
    
    class Meta:
        db_table = 'trips'
        verbose_name_plural = 'Trips'
        ordering = ['-created_at']

class TripDestination(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='destinations')
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    order = models.IntegerField()
    visit_date = models.DateField()
    estimated_arrival_time = models.TimeField()
    estimated_departure_time = models.TimeField()
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['order']
        db_table = 'trip_destinations'
    
    def __str__(self):
        return f"{self.trip.trip_name} - {self.destination.name}"

class Expense(models.Model):
    EXPENSE_CATEGORY = (
        ('transport', 'Transport'),
        ('accommodation', 'Accommodation'),
        ('food', 'Food'),
        ('entry_fee', 'Entry Fee'),
        ('shopping', 'Shopping'),
        ('miscellaneous', 'Miscellaneous'),
    )
    
    expense_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=50, choices=EXPENSE_CATEGORY)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200)
    expense_date = models.DateField()
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.category} - {self.amount} for {self.trip.trip_name}"
    
    class Meta:
        db_table = 'expenses'
        verbose_name_plural = 'Expenses'