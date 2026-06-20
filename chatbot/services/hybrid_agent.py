from django.db.models import Q, Sum

from destinations.models import Destination
from tours.models import Tour, TourBooking
from trips.models import Trip, Expense
from guides.models import Guide

from .agent import ColoGhuriChatbotAgent
from .intent_classifier import IntentClassifier
from .entities import (
    extract_price_filter,
    detect_destination_type,
    detect_booking_status,
)


class HybridColoGhuriChatbotAgent:
    def __init__(self, user=None, request=None):
        self.user = user
        self.request = request
        self.rule_agent = ColoGhuriChatbotAgent(user=user, request=request)
        self.classifier = IntentClassifier()

    def role(self):
        if not self.user or not self.user.is_authenticated:
            return 'guest'

        if self.user.is_staff or self.user.is_superuser or getattr(self.user, 'role', None) == 'admin':
            return 'admin'

        return getattr(self.user, 'role', 'guest') or 'guest'

    def is_authenticated(self):
        return self.user and self.user.is_authenticated

    def response(self, reply, cards=None, quick_replies=None, requires_confirmation=False, pending_action=None, nlu=None):
        return {
            'reply': reply,
            'cards': cards or [],
            'quick_replies': quick_replies or [],
            'requires_confirmation': requires_confirmation,
            'pending_action': pending_action,
            'nlu': nlu,
        }

    def default_quick_replies(self):
        role = self.role()

        if role == 'admin':
            return ['Admin dashboard', 'Pending guides', 'Contact messages', 'Activity logs']

        if role == 'guide':
            return ['Guide dashboard', 'Pending bookings', 'Recent bookings', 'Availability']

        if role == 'traveller':
            return ['Show tours', 'My bookings', 'My trips', 'My wishlist']

        return ['Show destinations', 'Show tours', 'How to register?', 'Payment methods']

    def role_allowed(self, intent):
        role = self.role()

        common = {
            'greeting',
            'help',
            'registration_help',
            'login_help',
            'payment_methods',
            'contact_support',
            'show_destinations',
            'destination_type_beach',
            'destination_type_hill',
            'destination_type_forest',
            'destination_type_historical',
            'destination_fee_under',
            'show_tours',
            'tour_price_under',
            'tour_price_over',
            'tour_price_between',
            'tour_available_seats',
            'tour_details',
            'booking_help',
            'map_help',
            'review_help',
            'fallback_general',
        }

        traveller = {
            'traveller_dashboard',
            'traveller_bookings',
            'traveller_booking_pending',
            'traveller_booking_confirmed',
            'traveller_booking_completed',
            'traveller_trips',
            'traveller_wishlist',
            'traveller_budget_summary',
            'booking_ticket',
        }

        guide = {
            'guide_dashboard',
            'guide_my_tours',
            'guide_pending_bookings',
            'guide_recent_bookings',
            'guide_confirmed_bookings',
            'guide_availability',
            'guide_payment_verification',
        }

        admin = {
            'admin_dashboard',
            'admin_users',
            'admin_pending_guides',
            'admin_destinations',
            'admin_tours',
            'admin_bookings',
            'admin_activity_logs',
            'admin_contact_messages',
            'unsafe_delete_action',
            'unsafe_update_action',
        }

        if intent in common:
            return True

        if role == 'traveller' and intent in traveller:
            return True

        if role == 'guide' and intent in guide:
            return True

        if role == 'admin' and intent in admin:
            return True

        return False

    def permission_message(self, intent, nlu):
        if not self.is_authenticated():
            return self.response(
                'Please login first. Traveller, guide, and admin features require login.',
                quick_replies=['Login', 'Show tours', 'Show destinations'],
                nlu=nlu
            )

        return self.response(
            f'This option is not available for your current role: {self.role()}.',
            quick_replies=self.default_quick_replies(),
            nlu=nlu
        )

    def card(self, title, description, url=None):
        return {
            'title': str(title),
            'description': str(description),
            'url': url or '',
            'link': url or '',
        }

    def navigation_response(self, title, description, url, quick_replies=None, nlu=None):
        return self.response(
            description,
            cards=[self.card(title, description, url)],
            quick_replies=quick_replies or self.default_quick_replies(),
            nlu=nlu
        )

    def destination_card(self, destination):
        rating = getattr(destination, 'average_rating', 0) or 0
        location = getattr(destination, 'location', '') or 'Location not added'
        destination_type = getattr(destination, 'destination_type', '') or 'Destination'

        return self.card(
            destination.name,
            f'{location} | Type: {destination_type} | Rating: {rating}',
            f'/destinations/{destination.destination_id}'
        )

    def tour_card(self, tour):
        guide_group = getattr(tour, 'guide_group', None)
        guide_name = getattr(guide_group, 'guide_groupname', 'Guide Group')
        price = getattr(tour, 'price_per_person', 0)
        seats = getattr(tour, 'available_seats', 0)
        status = getattr(tour, 'status', 'N/A')

        return self.card(
            tour.tour_name,
            f'Price: BDT {price} | Seats: {seats} | Status: {status} | Guide: {guide_name}',
            f'/tours/{tour.tour_id}'
        )

    def booking_card(self, booking):
        tour = booking.tour

        return self.card(
            f'Booking #{booking.booking_id} - {tour.tour_name}',
            f'Status: {booking.status} | Travellers: {booking.number_of_travellers} | Total: BDT {booking.total_amount}',
            '/my-bookings'
        )

    def show_destinations(self, message, intent=None, nlu=None):
        queryset = Destination.objects.all()

        destination_type = detect_destination_type(message)

        if intent == 'destination_type_beach':
            destination_type = 'beach'
        elif intent == 'destination_type_hill':
            destination_type = 'hill'
        elif intent == 'destination_type_forest':
            destination_type = 'forest'
        elif intent == 'destination_type_historical':
            destination_type = 'historical'

        if destination_type:
            queryset = queryset.filter(
                Q(destination_type__icontains=destination_type)
                | Q(name__icontains=destination_type)
                | Q(location__icontains=destination_type)
            )

        if intent == 'destination_fee_under':
            price_filter = extract_price_filter(message, default_mode='under')

            if price_filter['amount'] is not None:
                queryset = queryset.filter(entry_fee__lte=price_filter['amount'])

        queryset = queryset.order_by('-average_rating', 'name')[:6]
        destinations = list(queryset)

        if not destinations:
            return self.response(
                'No matching destinations found.',
                quick_replies=['Show all destinations', 'Beach destinations', 'Hill destinations'],
                nlu=nlu
            )

        return self.response(
            f'I found {len(destinations)} matching destination(s).',
            cards=[self.destination_card(destination) for destination in destinations],
            quick_replies=['Show tours', 'Beach destinations', 'Hill destinations'],
            nlu=nlu
        )

    def show_tours(self, message, intent=None, nlu=None):
        queryset = Tour.objects.select_related('guide_group').all()

        if intent in ['show_tours', 'tour_available_seats']:
            queryset = queryset.filter(status='upcoming')

        if intent == 'tour_available_seats':
            queryset = queryset.filter(available_seats__gt=0).order_by('-available_seats')
        else:
            queryset = queryset.order_by('price_per_person')

        tours = list(queryset[:6])

        if not tours:
            return self.response(
                'No matching tours found.',
                quick_replies=['Show destinations', 'Contact support'],
                nlu=nlu
            )

        return self.response(
            f'I found {len(tours)} tour package(s).',
            cards=[self.tour_card(tour) for tour in tours],
            quick_replies=['Tours under 5000', 'Tours over 5000', 'My bookings'],
            nlu=nlu
        )

    def show_tours_by_price(self, message, intent, nlu=None):
        price_filter = extract_price_filter(message)

        if intent == 'tour_price_under':
            price_filter['mode'] = 'under'
        elif intent == 'tour_price_over':
            price_filter['mode'] = 'over'
        elif intent == 'tour_price_between':
            price_filter['mode'] = 'between'

        queryset = Tour.objects.select_related('guide_group').filter(
            status='upcoming',
            available_seats__gt=0
        )

        mode = price_filter['mode']

        if mode == 'under':
            amount = price_filter['amount']

            if amount is None:
                return self.response(
                    'Please mention an amount. Example: tours under 5000 taka.',
                    quick_replies=['Tours under 5000', 'Tours under 10000'],
                    nlu=nlu
                )

            queryset = queryset.filter(price_per_person__lte=amount).order_by('price_per_person')
            title = f'Tours under BDT {amount}'
            empty = f'No upcoming tours found under BDT {amount}.'

        elif mode == 'over':
            amount = price_filter['amount']

            if amount is None:
                return self.response(
                    'Please mention an amount. Example: tours over 5000 taka.',
                    quick_replies=['Tours over 5000', 'Tours over 10000'],
                    nlu=nlu
                )

            queryset = queryset.filter(price_per_person__gte=amount).order_by('price_per_person')
            title = f'Tours over BDT {amount}'
            empty = f'No upcoming tours found over BDT {amount}.'

        elif mode == 'between':
            low = price_filter['low']
            high = price_filter['high']

            if low is None or high is None:
                return self.response(
                    'Please mention two amounts. Example: tours between 5000 and 10000.',
                    quick_replies=['Tours between 5000 and 10000', 'Tours under 5000'],
                    nlu=nlu
                )

            queryset = queryset.filter(
                price_per_person__gte=low,
                price_per_person__lte=high
            ).order_by('price_per_person')

            title = f'Tours between BDT {low} and BDT {high}'
            empty = f'No upcoming tours found between BDT {low} and BDT {high}.'

        else:
            return self.show_tours(message, nlu=nlu)

        tours = list(queryset[:6])

        if not tours:
            return self.response(
                empty,
                quick_replies=['Show all tours', 'Tours under 5000', 'Tours over 5000'],
                nlu=nlu
            )

        return self.response(
            f'{title}: I found {len(tours)} matching tour(s).',
            cards=[self.tour_card(tour) for tour in tours],
            quick_replies=['Show all tours', 'My bookings', 'Contact support'],
            nlu=nlu
        )

    def traveller_bookings(self, message, status_filter=None, nlu=None):
        if not self.is_authenticated():
            return self.permission_message('traveller_bookings', nlu)

        queryset = TourBooking.objects.filter(
            traveller=self.user
        ).select_related('tour', 'tour__guide_group')

        detected_status = status_filter or detect_booking_status(message)

        if detected_status:
            queryset = queryset.filter(status=detected_status)

        bookings = list(queryset.order_by('-booking_date')[:6])

        if not bookings:
            status_text = f' {detected_status}' if detected_status else ''
            return self.response(
                f'No{status_text} bookings found.',
                quick_replies=['Show tours', 'My trips', 'My wishlist'],
                nlu=nlu
            )

        return self.response(
            f'I found {len(bookings)} booking(s).',
            cards=[self.booking_card(booking) for booking in bookings],
            quick_replies=['Download ticket', 'My trips', 'Contact support'],
            nlu=nlu
        )

    def traveller_trips(self, nlu=None):
        trips = list(Trip.objects.filter(traveller=self.user).order_by('-created_at')[:6])

        if not trips:
            return self.response(
                'You do not have any trips yet.',
                quick_replies=['Show destinations', 'Show tours'],
                nlu=nlu
            )

        cards = [
            self.card(
                trip.trip_name,
                f'Status: {trip.status} | Budget: BDT {trip.total_budget}',
                '/my-trips'
            )
            for trip in trips
        ]

        return self.response(
            f'I found {len(trips)} trip(s).',
            cards=cards,
            quick_replies=['My bookings', 'Show destinations'],
            nlu=nlu
        )

    def traveller_budget_summary(self, nlu=None):
        trips = Trip.objects.filter(traveller=self.user)
        total_budget = trips.aggregate(total=Sum('total_budget'))['total'] or 0
        total_expense = Expense.objects.filter(trip__traveller=self.user).aggregate(total=Sum('amount'))['total'] or 0

        return self.response(
            f'Your total trip budget is BDT {total_budget}. Your recorded expense is BDT {total_expense}. Remaining budget is BDT {total_budget - total_expense}.',
            quick_replies=['My trips', 'My bookings'],
            nlu=nlu
        )

    def traveller_wishlist(self, nlu=None):
        try:
            from engagement.models import WishlistItem

            items = WishlistItem.objects.filter(user=self.user).select_related('destination', 'tour')[:6]
            cards = []

            for item in items:
                if item.destination:
                    cards.append(self.destination_card(item.destination))
                elif item.tour:
                    cards.append(self.tour_card(item.tour))

            if not cards:
                return self.response(
                    'Your wishlist is empty.',
                    quick_replies=['Show destinations', 'Show tours'],
                    nlu=nlu
                )

            return self.response(
                f'I found {len(cards)} saved item(s) in your wishlist.',
                cards=cards,
                quick_replies=['Show tours', 'Show destinations'],
                nlu=nlu
            )

        except Exception:
            return self.navigation_response(
                'My Wishlist',
                'Open your wishlist page to view saved tours and destinations.',
                '/my-wishlist',
                nlu=nlu
            )

    def guide_bookings(self, status_filter=None, nlu=None):
        try:
            guide = Guide.objects.get(user=self.user)
        except Guide.DoesNotExist:
            return self.response(
                'Guide profile not found. Please contact admin.',
                quick_replies=['Contact support'],
                nlu=nlu
            )

        queryset = TourBooking.objects.filter(
            tour__guide_group=guide.guide_group
        ).select_related('traveller', 'tour')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        bookings = list(queryset.order_by('-booking_date')[:6])

        if not bookings:
            return self.response(
                'No matching guide bookings found.',
                quick_replies=['Guide dashboard', 'Availability'],
                nlu=nlu
            )

        cards = [
            self.card(
                f'Booking #{booking.booking_id} - {booking.tour.tour_name}',
                f'Traveller: {booking.traveller.username} | Status: {booking.status} | Total: BDT {booking.total_amount}',
                '/guide/dashboard'
            )
            for booking in bookings
        ]

        return self.response(
            f'I found {len(bookings)} booking(s) for your guide group.',
            cards=cards,
            quick_replies=['Pending bookings', 'Recent bookings', 'Availability'],
            nlu=nlu
        )

    def admin_summary(self, nlu=None):
        total_users = self.safe_count(lambda: self.get_user_count())
        total_destinations = self.safe_count(lambda: Destination.objects.count())
        total_tours = self.safe_count(lambda: Tour.objects.count())
        total_bookings = self.safe_count(lambda: TourBooking.objects.count())

        return self.response(
            f'Admin summary: {total_users} verified users, {total_destinations} destinations, {total_tours} tours, and {total_bookings} bookings.',
            cards=[
                self.card('Admin Dashboard', 'Open admin dashboard for full platform overview.', '/admin'),
                self.card('Activity Logs', 'Monitor important system actions.', '/admin/activity-logs'),
                self.card('Contact Messages', 'View traveller and guide support messages.', '/admin/contact-messages')
            ],
            quick_replies=['Pending guides', 'Contact messages', 'Activity logs'],
            nlu=nlu
        )

    def get_user_count(self):
        from users.models import User
        return User.objects.filter(email_verified=True).count()

    def safe_count(self, func):
        try:
            return func()
        except Exception:
            return 0

    def unsafe_action_response(self, nlu=None):
        return self.response(
            'For safety, destructive or approval actions are not executed directly by the trained model. Please use the proper dashboard page or the existing confirmation-based chatbot command.',
            cards=[
                self.card('Admin Panel', 'Open admin panel to safely manage users, guides, destinations, tours, and bookings.', '/admin')
            ],
            quick_replies=['Admin dashboard', 'Activity logs'],
            nlu=nlu
        )

    def handle(self, message='', confirmed_action=None):
        if confirmed_action:
            return self.rule_agent.handle(message=message, confirmed_action=confirmed_action)

        message = (message or '').strip()

        if not message:
            return self.response(
                'Please type a message.',
                quick_replies=self.default_quick_replies()
            )

        nlu = self.classifier.predict(message)
        intent = nlu['intent']

        if not nlu['is_confident']:
            result = self.rule_agent.handle(message=message)
            result['nlu'] = nlu
            return result

        if not self.role_allowed(intent):
            return self.permission_message(intent, nlu)

        if intent == 'greeting':
            return self.response(
                'Hello! I am PothBondhu, your Colo Ghuri assistant. I can help with destinations, tours, booking, dashboard, guide tasks, and admin tasks based on your role.',
                quick_replies=self.default_quick_replies(),
                nlu=nlu
            )

        if intent == 'help':
            return self.response(
                'You can ask about destinations, tours, price filters, booking, payment, registration, traveller dashboard, guide bookings, guide availability, admin dashboard, contact messages, and activity logs.',
                quick_replies=self.default_quick_replies(),
                nlu=nlu
            )

        if intent == 'registration_help':
            return self.response(
                'You can register as a traveller or guide from the Register page. Guide users may need admin verification before managing tours.',
                cards=[self.card('Register', 'Create traveller or guide account.', '/register')],
                quick_replies=['Login help', 'Payment methods'],
                nlu=nlu
            )

        if intent == 'login_help':
            return self.response(
                'Please check your email/password and make sure your email is verified. If you still cannot login, contact admin support.',
                cards=[self.card('Login', 'Open login page.', '/login')],
                quick_replies=['Contact support', 'Register'],
                nlu=nlu
            )

        if intent == 'payment_methods':
            return self.response(
                'Colo Ghuri supports payment information and payment proof upload depending on the booking flow. After booking, follow the payment instruction and upload proof/transaction ID if required.',
                quick_replies=['Booking help', 'Contact support'],
                nlu=nlu
            )

        if intent == 'contact_support':
            if self.role() == 'admin':
                return self.navigation_response(
                    'Contact Messages',
                    'Admin users can view traveller and guide messages from the admin panel.',
                    '/admin/contact-messages',
                    nlu=nlu
                )

            return self.navigation_response(
                'Contact Support',
                'Open the contact page. Your name and email will be taken automatically from your logged-in account.',
                '/contact',
                nlu=nlu
            )

        if intent in [
            'show_destinations',
            'destination_type_beach',
            'destination_type_hill',
            'destination_type_forest',
            'destination_type_historical',
            'destination_fee_under',
        ]:
            return self.show_destinations(message, intent=intent, nlu=nlu)

        if intent in ['show_tours', 'tour_available_seats']:
            return self.show_tours(message, intent=intent, nlu=nlu)

        if intent in ['tour_price_under', 'tour_price_over', 'tour_price_between']:
            return self.show_tours_by_price(message, intent=intent, nlu=nlu)

        if intent == 'tour_details':
            return self.response(
                'Please open any tour card to see full details, itinerary, guide group, price, seats, reviews, and route map.',
                quick_replies=['Show tours', 'Tours under 5000'],
                nlu=nlu
            )

        if intent == 'booking_help':
            return self.response(
                'To book a tour, open a tour detail page, select required information, submit booking, then follow payment instructions if needed.',
                quick_replies=['Show tours', 'Payment methods'],
                nlu=nlu
            )

        if intent == 'map_help':
            return self.response(
                'Maps are available on destination detail and tour detail pages when latitude and longitude are added by admin.',
                quick_replies=['Show destinations', 'Show tours'],
                nlu=nlu
            )

        if intent == 'review_help':
            return self.response(
                'Travellers can review destinations from destination detail pages. Tour reviews are usually allowed after completing a booking.',
                quick_replies=['Show tours', 'Show destinations'],
                nlu=nlu
            )

        if intent == 'traveller_dashboard':
            return self.navigation_response(
                'Traveller Dashboard',
                'Open traveller dashboard for booking, trip, wishlist, budget, and notification summary.',
                '/traveller/dashboard',
                nlu=nlu
            )

        if intent == 'traveller_bookings':
            return self.traveller_bookings(message, nlu=nlu)

        if intent == 'traveller_booking_pending':
            return self.traveller_bookings(message, status_filter='pending', nlu=nlu)

        if intent == 'traveller_booking_confirmed':
            return self.traveller_bookings(message, status_filter='confirmed', nlu=nlu)

        if intent == 'traveller_booking_completed':
            return self.traveller_bookings(message, status_filter='completed', nlu=nlu)

        if intent == 'traveller_trips':
            return self.traveller_trips(nlu=nlu)

        if intent == 'traveller_wishlist':
            return self.traveller_wishlist(nlu=nlu)

        if intent == 'traveller_budget_summary':
            return self.traveller_budget_summary(nlu=nlu)

        if intent == 'booking_ticket':
            return self.response(
                'You can download your booking ticket/PDF invoice from Traveller Dashboard or My Bookings page.',
                cards=[
                    self.card('Traveller Dashboard', 'Open dashboard and click ticket beside your booking.', '/traveller/dashboard'),
                    self.card('My Bookings', 'Open your booking list.', '/my-bookings')
                ],
                quick_replies=['My bookings', 'Traveller dashboard'],
                nlu=nlu
            )

        if intent == 'guide_dashboard':
            return self.navigation_response(
                'Guide Dashboard',
                'Open your guide dashboard to view guide group summary, bookings, and tour performance.',
                '/guide/dashboard',
                nlu=nlu
            )

        if intent == 'guide_my_tours':
            return self.navigation_response(
                'Manage Tours',
                'Open guide tour management page to create and manage your guide group tours.',
                '/guide/tours',
                nlu=nlu
            )

        if intent == 'guide_pending_bookings':
            return self.guide_bookings(status_filter='pending', nlu=nlu)

        if intent == 'guide_recent_bookings':
            return self.guide_bookings(status_filter=None, nlu=nlu)

        if intent == 'guide_confirmed_bookings':
            return self.guide_bookings(status_filter='confirmed', nlu=nlu)

        if intent == 'guide_availability':
            return self.navigation_response(
                'Guide Availability',
                'Open availability calendar to manage available, unavailable, and booked dates.',
                '/guide/availability',
                nlu=nlu
            )

        if intent == 'guide_payment_verification':
            return self.response(
                'Payment proof verification should be handled from the guide dashboard or booking management section for safety.',
                cards=[self.card('Guide Dashboard', 'Open guide dashboard.', '/guide/dashboard')],
                quick_replies=['Pending bookings', 'Recent bookings'],
                nlu=nlu
            )

        if intent == 'admin_dashboard':
            return self.admin_summary(nlu=nlu)

        if intent == 'admin_users':
            return self.navigation_response(
                'Manage Users',
                'Open admin panel to manage travellers, guides, and users.',
                '/admin/users',
                nlu=nlu
            )

        if intent == 'admin_pending_guides':
            result = self.rule_agent.handle(message='pending guide groups')
            result['nlu'] = nlu
            return result

        if intent == 'admin_destinations':
            return self.navigation_response(
                'Manage Destinations',
                'Open admin panel to add, edit, or delete destinations.',
                '/admin/destinations',
                nlu=nlu
            )

        if intent == 'admin_tours':
            return self.navigation_response(
                'Manage Tours',
                'Open admin panel to manage tours.',
                '/admin/tours',
                nlu=nlu
            )

        if intent == 'admin_bookings':
            return self.navigation_response(
                'Manage Bookings',
                'Open admin panel to review platform bookings.',
                '/admin/bookings',
                nlu=nlu
            )

        if intent == 'admin_activity_logs':
            return self.navigation_response(
                'Activity Logs',
                'Open activity logs to monitor platform actions.',
                '/admin/activity-logs',
                nlu=nlu
            )

        if intent == 'admin_contact_messages':
            return self.navigation_response(
                'Contact Messages',
                'Open admin contact messages to view traveller and guide support messages.',
                '/admin/contact-messages',
                nlu=nlu
            )

        if intent in ['unsafe_delete_action', 'unsafe_update_action']:
            return self.unsafe_action_response(nlu=nlu)

        result = self.rule_agent.handle(message=message)
        result['nlu'] = nlu
        return result