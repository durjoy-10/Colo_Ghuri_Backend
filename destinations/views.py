from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend

from .models import Destination, DestinationImage
from .serializers import (
    DestinationSerializer,
    DestinationListSerializer,
    DestinationImageSerializer,
)


class DestinationListView(generics.ListAPIView):
    serializer_class = DestinationListSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location', 'description']
    ordering_fields = ['average_rating', 'entry_fee', 'name', 'created_at']

    def get_queryset(self):
        queryset = Destination.objects.prefetch_related('images').all()

        destination_type = self.request.query_params.get('destination_type')
        is_popular = self.request.query_params.get('is_popular')
        min_entry_fee = self.request.query_params.get('min_entry_fee')
        max_entry_fee = self.request.query_params.get('max_entry_fee')
        min_rating = self.request.query_params.get('min_rating')
        ordering = self.request.query_params.get('ordering')

        if destination_type:
            queryset = queryset.filter(destination_type=destination_type)

        if is_popular in ['true', 'True', '1']:
            queryset = queryset.filter(is_popular=True)

        if min_entry_fee:
            queryset = queryset.filter(entry_fee__gte=min_entry_fee)

        if max_entry_fee:
            queryset = queryset.filter(entry_fee__lte=max_entry_fee)

        if min_rating:
            queryset = queryset.filter(average_rating__gte=min_rating)

        ordering_map = {
            'rating_desc': '-average_rating',
            'rating_asc': 'average_rating',
            'entry_fee_asc': 'entry_fee',
            'entry_fee_desc': '-entry_fee',
            'name_asc': 'name',
            'name_desc': '-name',
            'newest': '-created_at',
            'oldest': 'created_at',
        }

        if ordering in ordering_map:
            queryset = queryset.order_by(ordering_map[ordering])
        else:
            queryset = queryset.order_by('-is_popular', '-average_rating', 'name')

        return queryset

class DestinationDetailView(generics.RetrieveAPIView):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'destination_id'


class DestinationCreateView(generics.CreateAPIView):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = (permissions.IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, *args, **kwargs):
        if request.content_type and request.content_type.startswith('application/json'):
            data = request.data
        else:
            data = request.data.dict() if hasattr(request.data, 'dict') else request.data

        destination_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'location': data.get('location'),
            'destination_type': data.get('destination_type'),
            'entry_fee': data.get('entry_fee', 0),
            'best_time_to_visit': data.get('best_time_to_visit', ''),
            'opening_hours': data.get('opening_hours', ''),
            'is_popular': data.get('is_popular', False),
        }

        serializer = self.get_serializer(data=destination_data)

        if serializer.is_valid():
            destination = serializer.save()

            if 'image' in request.FILES:
                DestinationImage.objects.create(
                    destination=destination,
                    image=request.FILES['image'],
                    is_primary=True,
                    order=1,
                )

            result_serializer = DestinationSerializer(
                destination,
                context={'request': request}
            )
            return Response(result_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DestinationUpdateView(generics.UpdateAPIView):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = (permissions.IsAdminUser,)
    lookup_field = 'destination_id'
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def put(self, request, *args, **kwargs):
        destination = self.get_object()

        if request.content_type and request.content_type.startswith('application/json'):
            data = request.data
        else:
            data = request.data.dict() if hasattr(request.data, 'dict') else request.data

        update_data = {
            'name': data.get('name', destination.name),
            'description': data.get('description', destination.description),
            'location': data.get('location', destination.location),
            'destination_type': data.get('destination_type', destination.destination_type),
            'entry_fee': data.get('entry_fee', destination.entry_fee),
            'best_time_to_visit': data.get('best_time_to_visit', destination.best_time_to_visit),
            'opening_hours': data.get('opening_hours', destination.opening_hours),
            'is_popular': data.get('is_popular', destination.is_popular),
        }

        serializer = self.get_serializer(destination, data=update_data, partial=True)

        if serializer.is_valid():
            destination = serializer.save()

            if 'image' in request.FILES:
                DestinationImage.objects.filter(
                    destination=destination,
                    is_primary=True
                ).delete()

                DestinationImage.objects.create(
                    destination=destination,
                    image=request.FILES['image'],
                    is_primary=True,
                    order=1,
                )

            result_serializer = DestinationSerializer(
                destination,
                context={'request': request}
            )
            return Response(result_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DestinationDeleteView(generics.DestroyAPIView):
    queryset = Destination.objects.all()
    permission_classes = (permissions.IsAdminUser,)
    lookup_field = 'destination_id'

    def destroy(self, request, *args, **kwargs):
        destination = self.get_object()
        DestinationImage.objects.filter(destination=destination).delete()
        destination.delete()

        return Response(
            {'message': 'Destination deleted successfully'},
            status=status.HTTP_200_OK
        )


class DestinationImageUploadView(generics.CreateAPIView):
    serializer_class = DestinationImageSerializer
    permission_classes = (permissions.IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        destination_id = request.data.get('destination')

        if not destination_id:
            return Response(
                {'error': 'Destination ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            destination = Destination.objects.get(destination_id=destination_id)
        except Destination.DoesNotExist:
            return Response(
                {'error': 'Destination not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if 'image' not in request.FILES:
            return Response(
                {'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_primary = str(request.data.get('is_primary', 'false')).lower() == 'true'

        if is_primary:
            DestinationImage.objects.filter(destination=destination).update(
                is_primary=False
            )

        image = DestinationImage.objects.create(
            destination=destination,
            image=request.FILES['image'],
            caption=request.data.get('caption', ''),
            is_primary=is_primary,
            order=DestinationImage.objects.filter(destination=destination).count() + 1,
        )

        serializer = DestinationImageSerializer(
            image,
            context={'request': request}
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DestinationImageDeleteView(generics.DestroyAPIView):
    queryset = DestinationImage.objects.all()
    permission_classes = (permissions.IsAdminUser,)
    lookup_field = 'id'
    lookup_url_kwarg = 'image_id'

    def destroy(self, request, *args, **kwargs):
        image = self.get_object()
        image.delete()

        return Response(
            {'message': 'Image deleted successfully'},
            status=status.HTTP_200_OK
        )