from io import BytesIO
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from .models import ActivityLog


def get_client_ip(request):
    if not request:
        return None

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]

    return request.META.get('REMOTE_ADDR')


def log_activity(actor=None, action_type='system', title='', description='', target_model='', target_id='', request=None):
    try:
        return ActivityLog.objects.create(
            actor=actor if actor and actor.is_authenticated else None,
            action_type=action_type,
            title=title,
            description=description,
            target_model=target_model,
            target_id=str(target_id) if target_id else '',
            ip_address=get_client_ip(request)
        )
    except Exception as e:
        print(f'Activity log failed: {str(e)}')
        return None


def create_in_app_notification(user, title, message, notification_type='general', link=''):
    try:
        from engagement.models import Notification

        if user:
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
    except Exception as e:
        print(f'Notification failed: {str(e)}')


def send_colo_email(to_email, subject, message):
    if not to_email:
        return False

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f'Email sending failed: {str(e)}')
        return False


def send_booking_created_email(booking):
    traveller = booking.traveller
    tour = booking.tour

    subject = f'Booking Received - {tour.tour_name}'
    message = f"""
Hello {traveller.first_name or traveller.username},

Your booking has been received successfully.

Booking ID: {booking.booking_id}
Tour: {tour.tour_name}
Travellers: {booking.number_of_travellers}
Total Amount: BDT {booking.total_amount}
Booking Status: {booking.status}

You can download your booking ticket from your dashboard.

Regards,
Colo Ghuri Team
"""

    send_colo_email(traveller.email, subject, message)

    create_in_app_notification(
        traveller,
        'Booking received',
        f'Your booking for {tour.tour_name} has been received.',
        'booking',
        '/my-bookings'
    )

    try:
        from guides.models import Guide

        guide_profiles = Guide.objects.filter(
            guide_group=tour.guide_group,
            user__isnull=False
        ).select_related('user')

        for guide_profile in guide_profiles:
            guide_user = guide_profile.user

            create_in_app_notification(
                guide_user,
                'New tour booking',
                f'{traveller.username} booked {tour.tour_name} for {booking.number_of_travellers} traveller(s).',
                'booking',
                '/guide/dashboard'
            )

            if guide_user.email:
                send_colo_email(
                    guide_user.email,
                    f'New Booking - {tour.tour_name}',
                    f"""
Hello {guide_user.first_name or guide_user.username},

A new booking has been placed for your tour.

Booking ID: {booking.booking_id}
Tour: {tour.tour_name}
Traveller: {traveller.get_full_name() or traveller.username}
Traveller Email: {traveller.email}
Number of Travellers: {booking.number_of_travellers}
Total Amount: BDT {booking.total_amount}
Payment Method: {booking.payment_method}
Booking Status: {booking.status}

Please check your guide dashboard.

Regards,
Colo Ghuri Team
"""
                )

    except Exception as e:
        print(f'Guide booking notification failed: {str(e)}')

    try:
        from users.models import User

        admins = User.objects.filter(role='admin')

        for admin in admins:
            create_in_app_notification(
                admin,
                'New booking created',
                f'{traveller.username} booked {tour.tour_name}.',
                'admin',
                '/admin'
            )

    except Exception as e:
        print(f'Admin booking notification failed: {str(e)}')


def send_booking_status_email(booking, old_status, new_status):
    traveller = booking.traveller
    tour = booking.tour

    subject = f'Booking Status Updated - {tour.tour_name}'
    message = f"""
Hello {traveller.first_name or traveller.username},

Your booking status has been updated.

Booking ID: {booking.booking_id}
Tour: {tour.tour_name}
Previous Status: {old_status}
New Status: {new_status}

Regards,
Colo Ghuri Team
"""

    send_colo_email(traveller.email, subject, message)

    create_in_app_notification(
        traveller,
        'Booking status updated',
        f'Your booking for {tour.tour_name} is now {new_status}.',
        'booking',
        '/my-bookings'
    )


def send_tour_completed_email(booking):
    traveller = booking.traveller
    tour = booking.tour

    subject = f'Tour Completed - {tour.tour_name}'
    message = f"""
Hello {traveller.first_name or traveller.username},

Your tour has been marked as completed.

Tour: {tour.tour_name}
Booking ID: {booking.booking_id}

You can now write a review for this tour.

Regards,
Colo Ghuri Team
"""

    send_colo_email(traveller.email, subject, message)

    create_in_app_notification(
        traveller,
        'Tour completed',
        f'{tour.tour_name} has been completed. You can now write a review.',
        'booking',
        f'/tours/{tour.tour_id}'
    )


def generate_booking_ticket_pdf(booking):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 30 * mm

    pdf.setTitle(f'Colo Ghuri Booking Ticket #{booking.booking_id}')

    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawString(25 * mm, y, 'Colo Ghuri')
    y -= 10 * mm

    pdf.setFont('Helvetica', 12)
    pdf.drawString(25 * mm, y, 'Official Booking Ticket / Invoice')
    y -= 18 * mm

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(25 * mm, y, f'Booking #{booking.booking_id}')
    y -= 12 * mm

    pdf.setFont('Helvetica', 11)

    rows = [
        ('Tour Name', booking.tour.tour_name),
        ('Guide Group', booking.tour.guide_group.guide_groupname),
        ('Traveller', booking.traveller.get_full_name() or booking.traveller.username),
        ('Email', booking.traveller.email),
        ('Number of Travellers', str(booking.number_of_travellers)),
        ('Total Amount', f'BDT {booking.total_amount}'),
        ('Booking Status', booking.status.upper()),
        ('Payment Method', booking.payment_method or 'N/A'),
        ('Transaction ID', booking.payment_id or 'N/A'),
        ('Guide Reference', booking.guide_reference or 'N/A'),
        ('Booking Date', booking.booking_date.strftime('%d %B %Y, %I:%M %p')),
    ]

    for label, value in rows:
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(25 * mm, y, f'{label}:')
        pdf.setFont('Helvetica', 11)
        pdf.drawString(75 * mm, y, str(value))
        y -= 9 * mm

    y -= 8 * mm
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(25 * mm, y, 'Important Note:')
    y -= 8 * mm

    pdf.setFont('Helvetica', 10)

    notes = [
        'Please keep this ticket with you during the tour.',
        'Show this ticket to the guide group if needed.',
        'Payment verification depends on guide/admin approval if manual payment is used.',
    ]

    for note in notes:
        pdf.drawString(30 * mm, y, f'- {note}')
        y -= 7 * mm

    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(25 * mm, 35 * mm, f'TICKET CODE: CG-{booking.booking_id}-{booking.traveller.id}')

    pdf.setFont('Helvetica', 9)
    pdf.drawString(25 * mm, 20 * mm, 'Generated by Colo Ghuri Travel Platform')

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="colo-ghuri-booking-{booking.booking_id}.pdf"'

    return response