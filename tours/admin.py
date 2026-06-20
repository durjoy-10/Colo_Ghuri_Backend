from django.contrib import admin
from .models import Tour, TourImage, TourDestination, FoodPlan, TourBooking

class TourImageInline(admin.TabularInline):
    model = TourImage
    extra = 3
    fields = ('image', 'caption', 'is_primary', 'order')
    readonly_fields = ('created_at',)
    classes = ('collapse',)


class FoodPlanInline(admin.TabularInline):
    model = FoodPlan
    extra = 3
    fields = ('day_number', 'meal_type', 'meal_description', 'meal_items', 'dietary_options')


class TourDestinationInline(admin.TabularInline):
    model = TourDestination
    extra = 1
    fields = ('destination', 'order', 'arrival_date', 'departure_date', 
              'arrival_time', 'departure_time', 'stay_duration_hours')
    inlines = [FoodPlanInline]


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ('tour_id', 'tour_name', 'guide_group', 'total_seats', 
                    'available_seats', 'price_per_person', 'status', 'get_cover_image_preview')
    list_filter = ('status', 'guide_group', 'created_at')
    search_fields = ('tour_name', 'description')
    readonly_fields = ('tour_id', 'created_at', 'updated_at', 'available_seats')
    inlines = [TourImageInline, TourDestinationInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('tour_name', 'guide_group', 'description', 'cover_image')
        }),
        ('Pricing & Availability', {
            'fields': ('total_seats', 'available_seats', 'price_per_person', 'discount_percentage')
        }),
        ('Status & Dates', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )
    
    def get_cover_image_preview(self, obj):
        if obj.cover_image:
            return f'<img src="{obj.cover_image.url}" width="50" height="50" style="object-fit:cover;" />'
        return 'No Image'
    get_cover_image_preview.allow_tags = True
    get_cover_image_preview.short_description = 'Cover Preview'


@admin.register(TourImage)
class TourImageAdmin(admin.ModelAdmin):
    list_display = ('image_id', 'tour', 'get_image_preview', 'is_primary', 'order', 'created_at')
    list_filter = ('is_primary', 'tour', 'created_at')
    search_fields = ('tour__tour_name', 'caption')
    readonly_fields = ('image_id', 'created_at')
    fieldsets = (
        ('Image Information', {
            'fields': ('tour', 'image', 'caption', 'is_primary', 'order')
        }),
        ('Metadata', {
            'fields': ('image_id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" width="50" height="50" style="object-fit:cover;" />'
        return 'No Image'
    get_image_preview.allow_tags = True
    get_image_preview.short_description = 'Preview'


@admin.register(TourDestination)
class TourDestinationAdmin(admin.ModelAdmin):
    list_display = ('tour', 'destination', 'order', 'arrival_date', 'departure_date')
    list_filter = ('tour', 'destination')
    search_fields = ('tour__tour_name', 'destination__name')
    inlines = [FoodPlanInline]


@admin.register(FoodPlan)
class FoodPlanAdmin(admin.ModelAdmin):
    list_display = ('tour_destination', 'day_number', 'meal_type', 'meal_items')
    list_filter = ('meal_type', 'day_number')
    search_fields = ('tour_destination__tour__tour_name',)


@admin.register(TourBooking)
class TourBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'tour', 'traveller', 'number_of_travellers', 
                    'total_amount', 'status', 'booking_date')
    list_filter = ('status', 'booking_date', 'payment_method')
    search_fields = ('traveller__username', 'tour__tour_name')
    readonly_fields = ('booking_id', 'booking_date')
    fieldsets = (
        ('Booking Information', {
            'fields': ('tour', 'traveller', 'number_of_travellers', 'total_amount')
        }),
        ('Payment & Status', {
            'fields': ('status', 'payment_method', 'payment_id', 'special_requests')
        }),
        ('Metadata', {
            'fields': ('booking_id', 'booking_date'),
            'classes': ('collapse',)
        }),
    )