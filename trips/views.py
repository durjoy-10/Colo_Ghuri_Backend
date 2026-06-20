from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db import IntegrityError
from .models import Trip, TripDestination, Expense
from .serializers import TripSerializer, TripDestinationSerializer, ExpenseSerializer


class TripListView(generics.ListCreateAPIView):
    serializer_class = TripSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Trip.objects.filter(traveller=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['traveller'] = request.user.id

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            try:
                self.perform_create(serializer)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except IntegrityError as exc:
                return Response({'error': f'Database error: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save(traveller=self.request.user)


class TripDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TripSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'trip_id'

    def get_queryset(self):
        return Trip.objects.filter(traveller=self.request.user)


class TripDestinationCreateView(generics.CreateAPIView):
    serializer_class = TripDestinationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        trip_id = request.data.get('trip')

        try:
            trip = Trip.objects.get(trip_id=trip_id, traveller=request.user)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(trip=trip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TripDestinationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TripDestinationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'id'
    lookup_url_kwarg = 'trip_destination_id'

    def get_queryset(self):
        return TripDestination.objects.filter(trip__traveller=self.request.user)

    def destroy(self, request, *args, **kwargs):
        trip_destination = self.get_object()
        trip_destination.delete()
        return Response({'message': 'Trip destination deleted successfully'}, status=status.HTTP_200_OK)


class ExpenseCreateView(generics.CreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        trip_id = request.data.get('trip')

        try:
            trip = Trip.objects.get(trip_id=trip_id, traveller=request.user)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(trip=trip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'expense_id'
    lookup_url_kwarg = 'expense_id'

    def get_queryset(self):
        return Expense.objects.filter(trip__traveller=self.request.user)

    def destroy(self, request, *args, **kwargs):
        expense = self.get_object()
        expense.delete()
        return Response({'message': 'Expense deleted successfully'}, status=status.HTTP_200_OK)