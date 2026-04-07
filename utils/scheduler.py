"""
APScheduler background job runner.
Runs inside the Flask process — no separate worker needed.

Jobs:
  send_booking_reminders — fires every 60 seconds,
    finds bookings starting in 25-35 minutes that haven't had a reminder sent,
    sends email + in-app notification to the user.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger    = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)


def send_booking_reminders(app):
    """Check for bookings starting in ~30 minutes and send reminders."""
    with app.app_context():
        from datetime import datetime, date, timedelta
        from extensions import db
        from models import Booking, Notification

        now          = datetime.now()   
        today        = date.today()
        window_start = (now + timedelta(minutes=25)).time()
        window_end   = (now + timedelta(minutes=35)).time()

        upcoming = Booking.query.filter(
            Booking.booking_date  == today,
            Booking.status.in_(['approved', 'paid']),
            Booking.reminder_sent == False,
            Booking.start_time    >= window_start,
            Booking.start_time    <= window_end,
        ).all()

        if not upcoming:
            return

        for booking in upcoming:
            try:
                # In-app push notification 
                db.session.add(Notification(
                    user_id    = booking.user_id,
                    message    = (f'Reminder: Your booking "{booking.title}" at '
                                  f'{booking.facility.name} starts in ~30 minutes '
                                  f'({booking.start_time.strftime("%H:%M")}).'),
                    type       = 'warning',
                    booking_id = booking.id,
                ))

                # Email reminder 
                from utils.email_service import send_booking_reminder
                try:
                    send_booking_reminder(booking)
                except Exception as e:
                    logger.warning(f'Reminder email failed for booking {booking.id}: {e}')

                booking.reminder_sent = True
                logger.info(f'Reminder sent: booking {booking.id} ({booking.title})')

            except Exception as e:
                logger.error(f'Reminder error for booking {booking.id}: {e}')

        db.session.commit()


def init_scheduler(app):
    """Initialise and start the scheduler. Call from create_app()."""
    if scheduler.running:
        return

    scheduler.add_job(
        func             = send_booking_reminders,
        args             = [app],
        trigger          = IntervalTrigger(seconds=60),
        id               = 'booking_reminders',
        name             = '30-min booking reminder',
        replace_existing = True,
        misfire_grace_time = 30,
    )
    scheduler.start()
    logger.info('APScheduler started — reminder job active')
