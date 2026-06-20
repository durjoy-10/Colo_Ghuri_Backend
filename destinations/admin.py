from django.contrib import admin
from .models import Destination, DestinationImage, DestinationMap

class DestinationImageInline(admin.TabularInline):
    model = DestinationImage
    extra = 1

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('destination_id', 'name', 'location', 'destination_type', 'entry_fee', 'average_rating', 'is_popular')
    list_filter = ('destination_type', 'is_popular')
    search_fields = ('name', 'location', 'description')
    inlines = [DestinationImageInline]

@admin.register(DestinationImage)
class DestinationImageAdmin(admin.ModelAdmin):
    list_display = ('destination', 'is_primary', 'order')
    list_filter = ('is_primary', 'destination')

@admin.register(DestinationMap)
class DestinationMapAdmin(admin.ModelAdmin):
    list_display = ('destination',)