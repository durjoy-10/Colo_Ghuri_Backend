import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.db.models import Q, Sum
from django.utils import timezone

from destinations.models import Destination
from tours.models import Tour, TourBooking
from trips.models import Trip, Expense
from guides.models import Guide, GuideGroup
from guides.utils import send_guide_acceptance_email
from users.models import User


class ColoGhuriChatbotAgent:
    """
    Rule-based role-aware chatbot agent for Colo Ghuri.

    This first version is intentionally safe:
    - Public read actions are allowed.
    - User-specific read actions require login.
    - Limited write actions require confirmation.
    - Dangerous delete/reject actions are not supported.
    """

    DESTINATION_TYPES = [
        'historical',
        'natural',
        'beach',
        'mountain',
        'religious',
        'adventure',
        'cultural',
    ]

    EXPENSE_CATEGORIES = [
        'transport',
        'accommodation',
        'food',
        'entry_fee',
        'shopping',
        'miscellaneous',
    ]

    BOOKING_STATUSES = [
        'pending',
        'confirmed',
        'cancelled',
        'completed',
    ]

    def __init__(self, user, request=None):
        self.user = user
        self.request = request

    # ---------------------------------------------------------
    # Main Handler
    # ---------------------------------------------------------

    def handle(self, message='', confirmed_action=None):
        if confirmed_action:
            return self.execute_confirmed_action(confirmed_action)

        message = (message or '').strip()
        lower = message.lower()

        if not message:
            return self.response(
                'Please type a message. You can ask me about destinations, tours, bookings, trips, or dashboard summary.',
                quick_replies=self.default_quick_replies()
            )

        if self.contains_any(lower, ['hello', 'hi', 'hey', 'assalamu', 'salam']):
            return self.greeting_response()

        if self.contains_any(lower, ['help', 'what can you do', 'commands']):
            return self.help_response()

        if self.contains_any(lower, ['what is colo ghuri', 'about colo ghuri', 'platform', 'website']):
            return self.platform_explanation()

        # Admin routes
        if self.is_admin():
            if self.contains_any(lower, ['admin summary', 'platform summary', 'dashboard summary', 'overall summary', 'system summary']):
                return self.admin_summary()

            if self.contains_any(lower, ['pending guide', 'pending group', 'guide group pending']):
                return self.pending_guide_groups()

            if self.contains_any(lower, ['verify guide group', 'approve guide group', 'verify group', 'approve group']):
                return self.prepare_verify_guide_group(lower)

        # Guide routes
        if self.role() == 'guide':
            if self.contains_any(lower, ['guide dashboard', 'my dashboard', 'revenue', 'profit', 'earning', 'income']):
                return self.guide_dashboard_summary()

            if self.contains_any(lower, ['pending booking', 'recent booking', 'my booking', 'bookings']):
                return self.guide_bookings(lower)

            if self.contains_any(lower, ['confirm booking', 'cancel booking', 'complete booking', 'mark booking']):
                return self.prepare_update_booking_status(lower)

        # Traveller routes
        if self.role() == 'traveller':
            if self.contains_any(lower, ['my booking', 'bookings']):
                return self.my_bookings()

            if self.contains_any(lower, ['my trip', 'trips', 'trip list']):
                return self.my_trips()

            if self.contains_any(lower, ['budget', 'spent', 'remaining', 'expense summary']):
                return self.trip_budget_summary(lower)

            if self.contains_any(lower, ['add expense', 'expense add', 'spent', 'cost']):
                return self.prepare_add_expense(lower, message)

        # Common public routes
        if self.contains_any(lower, ['destination', 'place', 'visit', 'tourist spot', 'spot']):
            return self.search_destinations(lower)

        if self.contains_any(lower, ['tour', 'package', 'available seats', 'seat', 'price', 'under', 'below']):
            return self.search_tours(lower)

        if self.contains_any(lower, ['register', 'signup', 'sign up', 'guide registration', 'traveller registration']):
            return self.registration_help()

        if self.contains_any(lower, ['payment', 'bkash', 'nagad', 'rocket', 'cash']):
            return self.payment_help()

        return self.fallback_response()

    # ---------------------------------------------------------
    # Response Format
    # ---------------------------------------------------------

    def response(
        self,
        reply,
        cards=None,
        quick_replies=None,
        requires_confirmation=False,
        pending_action=None
    ):
        return {
            'reply': reply,
            'cards': cards or [],
            'quick_replies': quick_replies or [],
            'requires_confirmation': requires_confirmation,
            'pending_action': pending_action,
        }

    def card(self, title, subtitle='', meta=None, url=None):
        return {
            'title': str(title),
            'subtitle': str(subtitle or ''),
            'meta': meta or [],
            'url': url,
        }

    def money(self, value):
        try:
            return f'{float(value):,.0f} BDT'
        except Exception:
            return f'{value} BDT'

    def role(self):
        if self.user and self.user.is_authenticated:
            return getattr(self.user, 'role', 'guest')
        return 'guest'

    def is_admin(self):
        return (
            self.user
            and self.user.is_authenticated
            and (
                getattr(self.user, 'role', None) == 'admin'
                or self.user.is_staff
                or self.user.is_superuser
            )
        )

    def contains_any(self, text, keywords):
        return any(keyword in text for keyword in keywords)

    def default_quick_replies(self):
        role = self.role()

        if role == 'guest':
            return [
                'Show destinations',
                'Show tours',
                'How to register?',
                'Payment methods',
            ]

        if role == 'traveller':
            return [
                'Show tours',
                'My bookings',
                'My trips',
                'Budget summary',
            ]

        if role == 'guide':
            return [
                'Guide dashboard',
                'Pending bookings',
                'Recent bookings',
                'Show tours',
            ]

        if self.is_admin():
            return [
                'Admin summary',
                'Pending guide groups',
                'Show destinations',
                'Show tours',
            ]

        return [
            'Show destinations',
            'Show tours',
        ]

    # ---------------------------------------------------------
    # General Responses
    # ---------------------------------------------------------

    def greeting_response(self):
        role = self.role()

        if role == 'guest':
            text = (
                'Hi, I am PothBondhu, your Colo Ghuri travel assistant. '
                'I can help you explore destinations, find tours, understand registration, and learn about payment methods.'
            )
        elif role == 'traveller':
            text = (
                f'Hi {self.user.username}, I am PothBondhu. '
                'I can help you find tours, check bookings, view trips, and add trip expenses.'
            )
        elif role == 'guide':
            text = (
                f'Hi {self.user.username}, I am PothBondhu. '
                'I can help you check your guide dashboard, bookings, revenue, and booking status.'
            )
        else:
            text = (
                f'Hi {self.user.username}, I am PothBondhu. '
                'I can help you monitor users, tours, destinations, and pending guide groups.'
            )

        return self.response(text, quick_replies=self.default_quick_replies())

    def help_response(self):
        role = self.role()

        if role == 'guest':
            text = (
                'You can ask me things like:\n'
                '- Show beach destinations\n'
                '- Show upcoming tours\n'
                '- Tours under 5000 taka\n'
                '- How can I register?\n'
                '- What payment methods are available?'
            )
        elif role == 'traveller':
            text = (
                'You can ask me things like:\n'
                '- Show tours under 3000 taka\n'
                '- Show my bookings\n'
                '- Show my trips\n'
                '- Budget summary\n'
                '- Add 500 food expense to trip 2'
            )
        elif role == 'guide':
            text = (
                'You can ask me things like:\n'
                '- Guide dashboard\n'
                '- Show pending bookings\n'
                '- Show recent bookings\n'
                '- Confirm booking 12\n'
                '- Cancel booking 15'
            )
        else:
            text = (
                'You can ask me things like:\n'
                '- Admin summary\n'
                '- Show pending guide groups\n'
                '- Verify guide group 3\n'
                '- Show destinations\n'
                '- Show tours'
            )

        return self.response(text, quick_replies=self.default_quick_replies())

    def platform_explanation(self):
        text = (
            'Colo Ghuri is a travel platform where travellers can explore destinations, '
            'book guided tours, create personal trip plans, and track expenses. '
            'Guide groups can register and manage tours after admin verification. '
            'Admins can manage destinations, tours, users, and guide group approval.'
        )

        return self.response(
            text,
            quick_replies=[
                'Show destinations',
                'Show tours',
                'How to register?',
                'Payment methods',
            ]
        )

    def registration_help(self):
        text = (
            'For traveller registration, click Register and create your traveller account. '
            'Then verify your email before login.\n\n'
            'For guide registration, use Guide Group Registration. After admin approval, '
            'each guide receives a password setup email and can then login as a guide.'
        )

        cards = [
            self.card(
                title='Traveller Registration',
                subtitle='Create a traveller account',
                url='/register'
            ),
            self.card(
                title='Guide Group Registration',
                subtitle='Register a guide group for admin verification',
                url='/guide-group-register'
            ),
        ]

        return self.response(text, cards=cards)

    def payment_help(self):
        text = (
            'Colo Ghuri currently supports bKash, Nagad, Rocket, and Cash payment options. '
            'For mobile payments, travellers enter a transaction ID. '
            'For cash payment, travellers select a guide reference.'
        )

        return self.response(text, quick_replies=['Show tours', 'My bookings'])

    def fallback_response(self):
        role = self.role()
    
        if self.is_admin():
            text = (
                'I could not fully understand that as an admin request.\n\n'
                'As an Admin, you can ask me things like:\n'
                '- Admin summary\n'
                '- Show pending guide groups\n'
                '- Verify guide group 3\n'
                '- Show tours\n'
                '- Show destinations\n\n'
                'Please try one of these admin commands.'
            )
    
            quick_replies = [
                'Admin summary',
                'Pending guide groups',
                'Show tours',
                'Show destinations',
            ]
    
        elif role == 'guide':
            text = (
                'I could not fully understand that as a guide request.\n\n'
                'As a Guide, you can ask me things like:\n'
                '- Guide dashboard\n'
                '- Show pending bookings\n'
                '- Show recent bookings\n'
                '- Confirm booking 12\n'
                '- Cancel booking 15\n\n'
                'Please try one of these guide commands.'
            )
    
            quick_replies = [
                'Guide dashboard',
                'Pending bookings',
                'Recent bookings',
                'Show tours',
            ]
    
        elif role == 'traveller':
            text = (
                'I could not fully understand that as a traveller request.\n\n'
                'As a Traveller, you can ask me things like:\n'
                '- Show tours under 5000 taka\n'
                '- Show my bookings\n'
                '- Show my trips\n'
                '- Budget summary for trip 1\n'
                '- Add 500 food expense to trip 1\n\n'
                'Please try one of these traveller commands.'
            )
    
            quick_replies = [
                'Show tours',
                'My bookings',
                'My trips',
                'Budget summary',
            ]
    
        else:
            text = (
                'I could not fully understand that.\n\n'
                'You are currently using the chatbot as a guest. You can ask me things like:\n'
                '- Show destinations\n'
                '- Show beach destinations\n'
                '- Show tours\n'
                '- Tours under 5000 taka\n'
                '- How can I register?\n'
                '- Payment methods\n\n'
                'Please login if you want to check bookings, trips, guide dashboard, or admin features.'
            )
    
            quick_replies = [
                'Show destinations',
                'Show tours',
                'How to register?',
                'Payment methods',
            ]
    
        return self.response(
            text,
            quick_replies=quick_replies
        )
    # ---------------------------------------------------------
    # Public Read: Destinations
    # ---------------------------------------------------------

    def search_destinations(self, lower):
        queryset = Destination.objects.all().order_by('-is_popular', 'name')

        matched_type = None
        for destination_type in self.DESTINATION_TYPES:
            if destination_type in lower:
                matched_type = destination_type
                break

        if matched_type:
            queryset = queryset.filter(destination_type=matched_type)

        if 'popular' in lower:
            queryset = queryset.filter(is_popular=True)

        tokens = self.extract_search_tokens(
            lower,
            remove_words=[
                'show', 'suggest', 'destination', 'destinations', 'place', 'places',
                'visit', 'best', 'tourist', 'spot', 'spots', 'popular'
            ] + self.DESTINATION_TYPES
        )

        if tokens and not matched_type:
            q_object = Q()
            for token in tokens:
                q_object |= Q(name__icontains=token)
                q_object |= Q(location__icontains=token)
                q_object |= Q(description__icontains=token)
            queryset = queryset.filter(q_object)

        destinations = list(queryset[:6])

        if not destinations:
            return self.response(
                'I could not find matching destinations. Try asking: "Show beach destinations" or "Show popular destinations".',
                quick_replies=['Show popular destinations', 'Show beach destinations', 'Show historical destinations']
            )

        cards = []
        for destination in destinations:
            cards.append(
                self.card(
                    title=destination.name,
                    subtitle=destination.location,
                    meta=[
                        f'Type: {destination.destination_type}',
                        f'Entry fee: {self.money(destination.entry_fee)}',
                        f'Best time: {destination.best_time_to_visit}',
                    ],
                    url=f'/destinations/{destination.destination_id}'
                )
            )

        reply = f'I found {len(destinations)} destination(s) for you.'
        return self.response(
            reply,
            cards=cards,
            quick_replies=['Show tours', 'Show popular destinations', 'Show beach destinations']
        )

    # ---------------------------------------------------------
    # Public Read: Tours
    # ---------------------------------------------------------

    def search_tours(self, lower):
        queryset = Tour.objects.select_related('guide_group').all()

        if self.role() == 'guest' or self.role() == 'traveller':
            queryset = queryset.filter(status='upcoming')

        if self.role() == 'guide':
            guide = self.get_guide()
            if guide:
                queryset = queryset.filter(guide_group=guide.guide_group)
            else:
                return self.response('Your guide profile was not found.')

        if 'upcoming' in lower:
            queryset = queryset.filter(status='upcoming')
        elif 'ongoing' in lower:
            queryset = queryset.filter(status='ongoing')
        elif 'completed' in lower:
            queryset = queryset.filter(status='completed')
        elif 'cancelled' in lower:
            queryset = queryset.filter(status='cancelled')

        if self.contains_any(lower, ['available seat', 'available seats', 'seat available']):
            queryset = queryset.filter(available_seats__gt=0)

        budget = self.extract_amount(lower)
        tours = list(queryset.order_by('-created_at'))

        if budget is not None:
            tours = [
                tour for tour in tours
                if Decimal(str(tour.final_price)) <= Decimal(str(budget))
            ]

        tours = tours[:6]

        if not tours:
            return self.response(
                'I could not find matching tours. Try asking: "Show upcoming tours" or "Tours under 5000 taka".',
                quick_replies=['Show upcoming tours', 'Tours under 5000 taka']
            )

        cards = []
        for tour in tours:
            cards.append(
                self.card(
                    title=tour.tour_name,
                    subtitle=tour.guide_group.guide_groupname,
                    meta=[
                        f'Status: {tour.status}',
                        f'Price: {self.money(tour.final_price)} per person',
                        f'Available seats: {tour.available_seats}/{tour.total_seats}',
                    ],
                    url=f'/tours/{tour.tour_id}'
                )
            )

        reply = f'I found {len(tours)} tour(s) for you.'
        return self.response(
            reply,
            cards=cards,
            quick_replies=['Show destinations', 'Tours under 5000 taka', 'My bookings']
        )

    # ---------------------------------------------------------
    # Traveller: Bookings, Trips, Expenses
    # ---------------------------------------------------------

    def my_bookings(self):
        if not self.require_login():
            return self.login_required_response('Please login as a traveller to view your bookings.')

        bookings = TourBooking.objects.filter(
            traveller=self.user
        ).select_related('tour').order_by('-booking_date')[:8]

        if not bookings:
            return self.response(
                'You do not have any bookings yet.',
                quick_replies=['Show tours']
            )

        cards = []
        for booking in bookings:
            cards.append(
                self.card(
                    title=f'Booking #{booking.booking_id}',
                    subtitle=booking.tour.tour_name,
                    meta=[
                        f'Status: {booking.status}',
                        f'Travellers: {booking.number_of_travellers}',
                        f'Total: {self.money(booking.total_amount)}',
                        f'Payment: {booking.payment_method or "Not provided"}',
                    ],
                    url=f'/tours/{booking.tour.tour_id}'
                )
            )

        return self.response(
            'Here are your latest bookings.',
            cards=cards,
            quick_replies=['Show tours', 'My trips']
        )

    def my_trips(self):
        if not self.require_login():
            return self.login_required_response('Please login as a traveller to view your trips.')

        trips = Trip.objects.filter(traveller=self.user).order_by('-created_at')[:8]

        if not trips:
            return self.response(
                'You do not have any personal trips yet.',
                quick_replies=['Show destinations', 'Show tours']
            )

        cards = []

        for trip in trips:
            spent = trip.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            remaining = trip.total_budget - spent

            cards.append(
                self.card(
                    title=f'{trip.trip_name} — Trip #{trip.trip_id}',
                    subtitle=f'{trip.start_date} to {trip.end_date}',
                    meta=[
                        f'Status: {trip.status}',
                        f'Budget: {self.money(trip.total_budget)}',
                        f'Spent: {self.money(spent)}',
                        f'Remaining: {self.money(remaining)}',
                    ],
                    url=f'/my-trips/{trip.trip_id}'
                )
            )

        return self.response(
            'Here are your latest trips.',
            cards=cards,
            quick_replies=['Budget summary', 'Add expense']
        )

    def trip_budget_summary(self, lower):
        if not self.require_login():
            return self.login_required_response('Please login as a traveller to view trip budget summary.')

        trips = Trip.objects.filter(traveller=self.user).order_by('-created_at')

        if not trips.exists():
            return self.response('You do not have any trips yet.')

        trip = self.find_trip_from_message(lower, trips)

        if not trip:
            return self.response(
                'Please mention the trip ID or trip name. Example: "budget summary for trip 2".',
                cards=[
                    self.card(
                        title=f'{t.trip_name} — Trip #{t.trip_id}',
                        subtitle=f'Budget: {self.money(t.total_budget)}',
                        url=f'/my-trips/{t.trip_id}'
                    )
                    for t in trips[:5]
                ]
            )

        spent = trip.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        remaining = trip.total_budget - spent

        text = (
            f'Budget summary for {trip.trip_name}:\n'
            f'Total budget: {self.money(trip.total_budget)}\n'
            f'Total spent: {self.money(spent)}\n'
            f'Remaining budget: {self.money(remaining)}'
        )

        return self.response(
            text,
            cards=[
                self.card(
                    title=trip.trip_name,
                    subtitle=f'{trip.start_date} to {trip.end_date}',
                    meta=[
                        f'Status: {trip.status}',
                        f'Budget: {self.money(trip.total_budget)}',
                        f'Spent: {self.money(spent)}',
                        f'Remaining: {self.money(remaining)}',
                    ],
                    url=f'/my-trips/{trip.trip_id}'
                )
            ],
            quick_replies=['My trips', 'Add expense']
        )

    def prepare_add_expense(self, lower, original_message):
        if not self.require_login():
            return self.login_required_response('Please login as a traveller to add an expense.')

        trips = Trip.objects.filter(traveller=self.user).order_by('-created_at')

        if not trips.exists():
            return self.response('You need to create a trip first before adding expenses.')

        amount = self.extract_amount(lower)
        category = self.extract_expense_category(lower)
        trip = self.find_trip_from_message(lower, trips)

        if not trip and trips.count() == 1:
            trip = trips.first()

        missing = []

        if not trip:
            missing.append('trip ID or trip name')
        if amount is None:
            missing.append('amount')
        if not category:
            missing.append('expense category')

        if missing:
            return self.response(
                'I need more information to add the expense. Missing: '
                + ', '.join(missing)
                + '. Example: "Add 500 food expense to trip 2".',
                cards=[
                    self.card(
                        title=f'{t.trip_name} — Trip #{t.trip_id}',
                        subtitle=f'Budget: {self.money(t.total_budget)}',
                        url=f'/my-trips/{t.trip_id}'
                    )
                    for t in trips[:5]
                ],
                quick_replies=['My trips', 'Budget summary']
            )

        description = self.clean_expense_description(original_message)
        expense_date = self.extract_date(lower) or timezone.localdate().isoformat()

        pending_action = {
            'type': 'add_expense',
            'trip_id': trip.trip_id,
            'amount': str(amount),
            'category': category,
            'description': description,
            'expense_date': expense_date,
        }

        text = (
            f'Please confirm this expense:\n'
            f'Trip: {trip.trip_name}\n'
            f'Category: {category}\n'
            f'Amount: {self.money(amount)}\n'
            f'Date: {expense_date}\n'
            f'Description: {description}'
        )

        return self.response(
            text,
            requires_confirmation=True,
            pending_action=pending_action,
            quick_replies=['Confirm', 'Cancel']
        )

    # ---------------------------------------------------------
    # Guide: Dashboard and Bookings
    # ---------------------------------------------------------

    def guide_dashboard_summary(self):
        if self.role() != 'guide':
            return self.response('Only guides can view guide dashboard summary.')

        guide = self.get_guide()

        if not guide:
            return self.response('Your guide profile was not found.')

        tours = Tour.objects.filter(guide_group=guide.guide_group)
        bookings = TourBooking.objects.filter(tour__in=tours)

        revenue = bookings.filter(
            status__in=['confirmed', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        expenses = tours.aggregate(total=Sum('total_expenses'))['total'] or Decimal('0.00')
        profit = revenue - expenses

        text = (
            f'Guide dashboard summary for {guide.guide_group.guide_groupname}:\n'
            f'Total tours: {tours.count()}\n'
            f'Total bookings: {bookings.count()}\n'
            f'Total revenue: {self.money(revenue)}\n'
            f'Total expenses: {self.money(expenses)}\n'
            f'Net profit: {self.money(profit)}'
        )

        cards = [
            self.card(
                title='Guide Dashboard',
                subtitle=guide.guide_group.guide_groupname,
                meta=[
                    f'Tours: {tours.count()}',
                    f'Bookings: {bookings.count()}',
                    f'Revenue: {self.money(revenue)}',
                    f'Profit: {self.money(profit)}',
                ],
                url='/guide/dashboard'
            )
        ]

        return self.response(
            text,
            cards=cards,
            quick_replies=['Pending bookings', 'Recent bookings', 'Show tours']
        )

    def guide_bookings(self, lower):
        if self.role() != 'guide':
            return self.response('Only guides can view guide booking information.')

        guide = self.get_guide()

        if not guide:
            return self.response('Your guide profile was not found.')

        tours = Tour.objects.filter(guide_group=guide.guide_group)
        bookings = TourBooking.objects.filter(
            tour__in=tours
        ).select_related('tour', 'traveller').order_by('-booking_date')

        if 'pending' in lower:
            bookings = bookings.filter(status='pending')

        bookings = bookings[:10]

        if not bookings:
            return self.response(
                'No bookings found.',
                quick_replies=['Guide dashboard', 'Show tours']
            )

        cards = []

        for booking in bookings:
            traveller_name = booking.traveller.get_full_name() or booking.traveller.username

            cards.append(
                self.card(
                    title=f'Booking #{booking.booking_id}',
                    subtitle=f'{booking.tour.tour_name} — {traveller_name}',
                    meta=[
                        f'Status: {booking.status}',
                        f'Travellers: {booking.number_of_travellers}',
                        f'Total: {self.money(booking.total_amount)}',
                        f'Payment: {booking.payment_method or "Not provided"}',
                    ],
                    url='/guide/dashboard'
                )
            )

        return self.response(
            'Here are the matching bookings.',
            cards=cards,
            quick_replies=['Guide dashboard', 'Pending bookings']
        )

    def prepare_update_booking_status(self, lower):
        if self.role() != 'guide':
            return self.response('Only guides can update booking status.')

        booking_id = self.extract_id(lower, keywords=['booking'])
        new_status = self.extract_booking_status(lower)

        if not booking_id:
            return self.response('Please mention the booking ID. Example: "Confirm booking 12".')

        if not new_status:
            return self.response(
                'Please mention the new status: pending, confirmed, cancelled, or completed.'
            )

        guide = self.get_guide()

        if not guide:
            return self.response('Your guide profile was not found.')

        try:
            booking = TourBooking.objects.select_related('tour').get(booking_id=booking_id)
        except TourBooking.DoesNotExist:
            return self.response('Booking not found.')

        if booking.tour.guide_group != guide.guide_group:
            return self.response('You cannot update a booking from another guide group.')

        pending_action = {
            'type': 'update_booking_status',
            'booking_id': booking.booking_id,
            'status': new_status,
        }

        text = (
            f'Please confirm booking status update:\n'
            f'Booking: #{booking.booking_id}\n'
            f'Tour: {booking.tour.tour_name}\n'
            f'Current status: {booking.status}\n'
            f'New status: {new_status}'
        )

        return self.response(
            text,
            requires_confirmation=True,
            pending_action=pending_action,
            quick_replies=['Confirm', 'Cancel']
        )

    # ---------------------------------------------------------
    # Admin: Summary and Guide Verification
    # ---------------------------------------------------------

    def admin_summary(self):
        if not self.is_admin():
            return self.response('Only admin can view platform summary.')

        total_users = User.objects.count()
        travellers = User.objects.filter(role='traveller').count()
        guides = User.objects.filter(role='guide').count()
        admins = User.objects.filter(role='admin').count()

        destinations = Destination.objects.count()
        tours = Tour.objects.count()
        bookings = TourBooking.objects.count()
        guide_groups = GuideGroup.objects.count()
        pending_groups = GuideGroup.objects.filter(is_verified=False).count()

        text = (
            'Platform summary:\n'
            f'Total users: {total_users}\n'
            f'Travellers: {travellers}\n'
            f'Guides: {guides}\n'
            f'Admins: {admins}\n'
            f'Destinations: {destinations}\n'
            f'Tours: {tours}\n'
            f'Bookings: {bookings}\n'
            f'Guide groups: {guide_groups}\n'
            f'Pending guide groups: {pending_groups}'
        )

        cards = [
            self.card(
                title='Users',
                subtitle=f'{total_users} total users',
                meta=[
                    f'Travellers: {travellers}',
                    f'Guides: {guides}',
                    f'Admins: {admins}',
                ],
                url='/admin/users'
            ),
            self.card(
                title='Travel Data',
                subtitle='Destinations, tours, and bookings',
                meta=[
                    f'Destinations: {destinations}',
                    f'Tours: {tours}',
                    f'Bookings: {bookings}',
                ],
                url='/admin'
            ),
            self.card(
                title='Guide Groups',
                subtitle=f'{pending_groups} pending',
                meta=[
                    f'Total groups: {guide_groups}',
                    f'Pending groups: {pending_groups}',
                ],
                url='/admin/guide-groups'
            ),
        ]

        return self.response(
            text,
            cards=cards,
            quick_replies=['Pending guide groups', 'Show tours', 'Show destinations']
        )

    def pending_guide_groups(self):
        if not self.is_admin():
            return self.response('Only admin can view pending guide groups.')

        groups = GuideGroup.objects.filter(is_verified=False).order_by('-created_at')[:10]

        if not groups:
            return self.response(
                'No pending guide groups found.',
                quick_replies=['Admin summary']
            )

        cards = []

        for group in groups:
            cards.append(
                self.card(
                    title=f'{group.guide_groupname} — Group #{group.guide_group_id}',
                    subtitle=group.email or 'No email provided',
                    meta=[
                        f'Members: {group.guide_group_number}',
                        f'Phone: {group.phone_number or "Not provided"}',
                        f'Created: {group.created_at.date()}',
                    ],
                    url='/admin/guide-groups'
                )
            )

        return self.response(
            'Here are pending guide groups.',
            cards=cards,
            quick_replies=['Admin summary']
        )

    def prepare_verify_guide_group(self, lower):
        if not self.is_admin():
            return self.response('Only admin can verify guide groups.')

        group_id = self.extract_id(lower, keywords=['group', 'guide group'])

        if not group_id:
            return self.response('Please mention the guide group ID. Example: "Verify guide group 3".')

        try:
            guide_group = GuideGroup.objects.get(guide_group_id=group_id)
        except GuideGroup.DoesNotExist:
            return self.response('Guide group not found.')

        if guide_group.is_verified:
            return self.response('This guide group is already verified.')

        pending_action = {
            'type': 'verify_guide_group',
            'guide_group_id': guide_group.guide_group_id,
        }

        text = (
            f'Please confirm guide group verification:\n'
            f'Group: {guide_group.guide_groupname}\n'
            f'Members: {guide_group.guide_group_number}\n'
            f'Email: {guide_group.email or "Not provided"}\n\n'
            f'After confirmation, password setup emails will be sent to the guides.'
        )

        return self.response(
            text,
            requires_confirmation=True,
            pending_action=pending_action,
            quick_replies=['Confirm', 'Cancel']
        )

    # ---------------------------------------------------------
    # Confirmed Actions
    # ---------------------------------------------------------

    def execute_confirmed_action(self, action):
        action_type = action.get('type')

        if action_type == 'add_expense':
            return self.execute_add_expense(action)

        if action_type == 'update_booking_status':
            return self.execute_update_booking_status(action)

        if action_type == 'verify_guide_group':
            return self.execute_verify_guide_group(action)

        return self.response('Unknown action. Nothing was changed.')

    def execute_add_expense(self, action):
        if self.role() != 'traveller':
            return self.response('Only travellers can add expenses.')

        try:
            trip = Trip.objects.get(
                trip_id=action.get('trip_id'),
                traveller=self.user
            )
        except Trip.DoesNotExist:
            return self.response('Trip not found.')

        try:
            amount = Decimal(str(action.get('amount')))
        except (InvalidOperation, TypeError):
            return self.response('Invalid expense amount.')

        category = action.get('category')

        if category not in self.EXPENSE_CATEGORIES:
            return self.response('Invalid expense category.')

        expense_date = action.get('expense_date') or timezone.localdate().isoformat()

        try:
            parsed_date = datetime.strptime(expense_date, '%Y-%m-%d').date()
        except ValueError:
            parsed_date = timezone.localdate()

        description = action.get('description') or 'Added by PothBondhu'

        expense = Expense.objects.create(
            trip=trip,
            category=category,
            amount=amount,
            description=description[:200],
            expense_date=parsed_date,
        )

        spent = trip.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        remaining = trip.total_budget - spent

        text = (
            f'Expense added successfully.\n'
            f'Trip: {trip.trip_name}\n'
            f'Expense ID: #{expense.expense_id}\n'
            f'Amount: {self.money(expense.amount)}\n'
            f'Total spent now: {self.money(spent)}\n'
            f'Remaining budget: {self.money(remaining)}'
        )

        return self.response(
            text,
            cards=[
                self.card(
                    title=f'{trip.trip_name}',
                    subtitle='Updated budget summary',
                    meta=[
                        f'Total budget: {self.money(trip.total_budget)}',
                        f'Spent: {self.money(spent)}',
                        f'Remaining: {self.money(remaining)}',
                    ],
                    url=f'/my-trips/{trip.trip_id}'
                )
            ],
            quick_replies=['My trips', 'Budget summary']
        )

    def execute_update_booking_status(self, action):
        if self.role() != 'guide':
            return self.response('Only guides can update booking status.')

        guide = self.get_guide()

        if not guide:
            return self.response('Your guide profile was not found.')

        booking_id = action.get('booking_id')
        new_status = action.get('status')

        if new_status not in self.BOOKING_STATUSES:
            return self.response('Invalid booking status.')

        try:
            booking = TourBooking.objects.select_related('tour').get(booking_id=booking_id)
        except TourBooking.DoesNotExist:
            return self.response('Booking not found.')

        if booking.tour.guide_group != guide.guide_group:
            return self.response('You cannot update a booking from another guide group.')

        old_status = booking.status

        if new_status == 'cancelled':
            booking.cancel()
        else:
            booking.status = new_status
            booking.save()

        text = (
            f'Booking #{booking.booking_id} updated successfully.\n'
            f'Old status: {old_status}\n'
            f'New status: {booking.status}'
        )

        return self.response(
            text,
            cards=[
                self.card(
                    title=f'Booking #{booking.booking_id}',
                    subtitle=booking.tour.tour_name,
                    meta=[
                        f'Status: {booking.status}',
                        f'Travellers: {booking.number_of_travellers}',
                        f'Total: {self.money(booking.total_amount)}',
                    ],
                    url='/guide/dashboard'
                )
            ],
            quick_replies=['Pending bookings', 'Guide dashboard']
        )

    def execute_verify_guide_group(self, action):
        if not self.is_admin():
            return self.response('Only admin can verify guide groups.')

        group_id = action.get('guide_group_id')

        try:
            guide_group = GuideGroup.objects.get(guide_group_id=group_id)
        except GuideGroup.DoesNotExist:
            return self.response('Guide group not found.')

        if guide_group.is_verified:
            return self.response('This guide group is already verified.')

        guide_group.is_verified = True
        guide_group.save()

        emails_sent = 0
        for guide in guide_group.guides.all():
            if send_guide_acceptance_email(guide, guide_group, self.request):
                emails_sent += 1

        text = (
            f'Guide group verified successfully.\n'
            f'Group: {guide_group.guide_groupname}\n'
            f'Password setup emails sent: {emails_sent}'
        )

        return self.response(
            text,
            cards=[
                self.card(
                    title=guide_group.guide_groupname,
                    subtitle='Verified guide group',
                    meta=[
                        f'Members: {guide_group.guide_group_number}',
                        f'Emails sent: {emails_sent}',
                    ],
                    url='/admin/guide-groups'
                )
            ],
            quick_replies=['Pending guide groups', 'Admin summary']
        )

    # ---------------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------------

    def require_login(self):
        return self.user and self.user.is_authenticated

    def login_required_response(self, message):
        return self.response(
            message,
            cards=[
                self.card(
                    title='Login required',
                    subtitle='Please login to continue',
                    url='/login'
                )
            ],
            quick_replies=['Show destinations', 'Show tours']
        )

    def get_guide(self):
        try:
            return Guide.objects.get(user=self.user)
        except Guide.DoesNotExist:
            return None

    def extract_search_tokens(self, lower, remove_words=None):
        remove_words = remove_words or []
        words = re.findall(r'[a-zA-Z]+', lower)

        tokens = []

        for word in words:
            if len(word) <= 2:
                continue
            if word in remove_words:
                continue
            if word in ['the', 'and', 'for', 'with', 'from', 'under', 'below', 'less', 'than', 'taka', 'bdt']:
                continue
            tokens.append(word)

        return tokens[:5]

    def extract_amount(self, lower):
        patterns = [
            r'(?:under|below|less than|max|maximum|within)\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:taka|bdt)',
            r'(\d+(?:\.\d+)?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                try:
                    return Decimal(match.group(1))
                except Exception:
                    return None

        return None

    def extract_id(self, lower, keywords=None):
        keywords = keywords or []

        for keyword in keywords:
            pattern = rf'{keyword}\s*(?:id)?\s*#?(\d+)'
            match = re.search(pattern, lower)
            if match:
                return int(match.group(1))

        match = re.search(r'#(\d+)', lower)
        if match:
            return int(match.group(1))

        match = re.search(r'\b(\d+)\b', lower)
        if match:
            return int(match.group(1))

        return None

    def extract_expense_category(self, lower):
        if 'entry fee' in lower or 'entry-fee' in lower:
            return 'entry_fee'

        for category in self.EXPENSE_CATEGORIES:
            if category in lower:
                return category

        return None

    def extract_booking_status(self, lower):
        if 'confirm' in lower:
            return 'confirmed'
        if 'cancel' in lower:
            return 'cancelled'
        if 'complete' in lower:
            return 'completed'
        if 'pending' in lower:
            return 'pending'

        for status_value in self.BOOKING_STATUSES:
            if status_value in lower:
                return status_value

        return None

    def extract_date(self, lower):
        match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', lower)
        if match:
            return match.group(1)
        return None

    def find_trip_from_message(self, lower, trips):
        trip_id = self.extract_id(lower, keywords=['trip'])

        if trip_id:
            try:
                return trips.get(trip_id=trip_id)
            except Trip.DoesNotExist:
                return None

        for trip in trips:
            if trip.trip_name.lower() in lower:
                return trip

        return None

    def clean_expense_description(self, original_message):
        description = original_message.strip()

        if len(description) > 180:
            description = description[:180]

        return description or 'Added by PothBondhu'