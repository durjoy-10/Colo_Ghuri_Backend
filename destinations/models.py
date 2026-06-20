from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Destination(models.Model):
    DESTINATION_TYPE = (
        ('historical', 'Historical'),
        ('natural', 'Natural'),
        ('beach', 'Beach'),
        ('mountain', 'Mountain'),
        ('religious', 'Religious'),
        ('adventure', 'Adventure'),
        ('cultural', 'Cultural'),
    )
    
    destination_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=300)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    destination_type = models.CharField(max_length=50, choices=DESTINATION_TYPE)
    entry_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    best_time_to_visit = models.CharField(max_length=200)
    opening_hours = models.CharField(max_length=200)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.IntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'destinations'
        verbose_name_plural = 'Destinations'

class DestinationImage(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='destination_images/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        db_table = 'destination_images'
    
    def __str__(self):
        return f"Image for {self.destination.name}"

class DestinationMap(models.Model):
    destination = models.OneToOneField(Destination, on_delete=models.CASCADE, related_name='map')
    map_image = models.ImageField(upload_to='destination_maps/')
    map_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"Map for {self.destination.name}"
    
    class Meta:
        db_table = 'destination_maps'