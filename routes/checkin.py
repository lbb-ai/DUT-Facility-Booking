"""
Check-in blueprint.
  GET  /checkin/<token>         — scan result (staff sees this after scanner opens URL)
  POST /checkin/<token>/confirm — mark attended
  GET  /scan                    — manual token entry fallback page
  POST /scan/lookup             — manual token lookup
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Booking, Notification
from datetime import datetime, date
from functools import wraps

checkin = Blueprint('checkin', __name__)


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access the check-in system.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_staff():
            flash('Check-in requires staff or admin access.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@checkin.route('/checkin/<token>')
@login_required
@staff_required
def scan_result(token):
    booking = Booking.query.filter_by(qr_token=token).first()

    if not booking:
        return render_template('checkin/invalid.html',
            reason='QR code not recognised. It may be invalid or from another system.')

    if booking.status in ['cancelled', 'rejected']:
        return render_template('checkin/invalid.html',
            reason=f'This booking was {booking.status} and cannot be checked in.')

    if booking.status not in ['approved', 'paid']:
        return render_template('checkin/invalid.html',
            reason=f'Booking status is "{booking.status}" — only approved/paid bookings can check in.')

    if booking.is_attended:
        return render_template('checkin/already_attended.html', booking=booking)

    now   = datetime.now()
    today = date.today()

    # Must be on the actual booking date
    if booking.booking_date != today:
        if booking.booking_date < today:
            return render_template('checkin/invalid.html',
                reason=f'This booking was for {booking.booking_date.strftime("%d %b %Y")} — the session has already passed.')
        else:
            days_ahead = (booking.booking_date - today).days
            return render_template('checkin/invalid.html',
                reason=f'This booking is for {booking.booking_date.strftime("%d %b %Y")} — '
                       f'QR check-in opens 1 hour before the session starts '
                       f'({days_ahead} day{"s" if days_ahead != 1 else ""} away).')

    # Must be within 1 hour before start time (or during the session)
    from datetime import timedelta, time as dtime
    session_start = datetime.combine(booking.booking_date, booking.start_time)
    session_end   = datetime.combine(booking.booking_date, booking.end_time)
    window_open   = session_start - timedelta(hours=1)

    if now < window_open:
        opens_in_mins = int((window_open - now).total_seconds() / 60)
        return render_template('checkin/too_early.html',
            booking=booking, opens_at=window_open, opens_in_mins=opens_in_mins)

    if now > session_end:
        return render_template('checkin/invalid.html',
            reason=f'The session ended at {booking.end_time.strftime("%H:%M")} — check-in is no longer available.')

    return render_template('checkin/scan_result.html', booking=booking)


@checkin.route('/checkin/<token>/confirm', methods=['POST'])
@login_required
@staff_required
def confirm_attendance(token):
    booking = Booking.query.filter_by(qr_token=token).first()

    if not booking:
        flash('Invalid QR token.', 'danger')
        return redirect(url_for('checkin.scan_page'))

    if booking.is_attended:
        flash(f'Already checked in at {booking.attended_at.strftime("%H:%M on %d %b %Y")}.', 'warning')
        return redirect(url_for('checkin.scan_result', token=token))

    if booking.status not in ['approved', 'paid']:
        flash('Cannot check in this booking.', 'danger')
        return redirect(url_for('checkin.scan_result', token=token))

    booking.attended_at    = datetime.utcnow()
    booking.attended_by_id = current_user.id

    db.session.add(Notification(
        user_id    = booking.user_id,
        message    = (f'✅ Check-in confirmed for "{booking.title}" at '
                      f'{booking.facility.name} on '
                      f'{booking.booking_date.strftime("%d %b %Y")} '
                      f'at {booking.attended_at.strftime("%H:%M")}.'),
        type       = 'success',
        booking_id = booking.id,
    ))
    db.session.commit()

    # Send confirmation email
    try:
        from utils.email_service import send_checkin_confirmed
        send_checkin_confirmed(booking, current_user)
    except Exception:
        pass

    return render_template('checkin/success.html', booking=booking)


@checkin.route('/scan')
@login_required
@staff_required
def scan_page():
    """Manual token entry — fallback when physical scanner isn't available."""
    return render_template('checkin/scan_page.html')


@checkin.route('/scan/lookup', methods=['POST'])
@login_required
@staff_required
def manual_lookup():
    token = request.form.get('token', '').strip()
    if not token:
        flash('Please enter a booking token.', 'warning')
        return redirect(url_for('checkin.scan_page'))
    return redirect(url_for('checkin.scan_result', token=token))
