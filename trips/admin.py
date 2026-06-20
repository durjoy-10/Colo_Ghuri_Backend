from django.contrib import admin
from .models import Trip, TripDestination, Expense

class TripDestinationInline(admin.TabularInline):
    model = TripDestination
    extra = 1

class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 1

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('trip_id', 'trip_name', 'traveller', 'start_date', 'end_date', 'total_budget', 'status')
    list_filter = ('status', 'start_date')
    search_fields = ('trip_name', 'traveller__username')
    inlines = [TripDestinationInline, ExpenseInline]

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_id', 'trip', 'category', 'amount', 'expense_date')
    list_filter = ('category', 'expense_date')