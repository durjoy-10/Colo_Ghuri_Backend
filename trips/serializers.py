from rest_framework import serializers
from django.db import models
from .models import Trip, TripDestination, Expense
from destinations.serializers import DestinationSerializer

class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ('expense_id',)

class TripDestinationSerializer(serializers.ModelSerializer):
    destination_details = DestinationSerializer(source='destination', read_only=True)
    
    class Meta:
        model = TripDestination
        fields = '__all__'

class TripSerializer(serializers.ModelSerializer):
    destinations = TripDestinationSerializer(many=True, read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True)
    total_expenses = serializers.SerializerMethodField()
    
    class Meta:
        model = Trip
        fields = ('trip_id', 'trip_name', 'start_date', 'end_date', 'total_budget', 
                  'status', 'notes', 'created_at', 'updated_at', 'traveller', 
                  'destinations', 'expenses', 'total_expenses')
        read_only_fields = ('trip_id', 'created_at', 'updated_at')
        extra_kwargs = {
            'traveller': {'required': False}
        }
    
    def get_total_expenses(self, obj):
        return obj.expenses.aggregate(total=models.Sum('amount'))['total'] or 0
    
    def validate(self, data):
        print(f"Validating data: {data}")
        return data