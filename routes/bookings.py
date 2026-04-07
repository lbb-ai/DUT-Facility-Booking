from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
from extensions import db
from models import Booking, Facility, Notification, FacilityRating
from utils.email_service import (send_booking_confirmation, send_booking_cancelled,
                                  send_admin_new_request, send_booking_rescheduled)
from utils.pdf_generator import generate_confirmation_html, try_generate_pdf_bytes
from datetime import date, datetime, timedelta

bookings = Blueprint('bookings', __name__)


@bookings.route('/bookings')
@login_required
def list_bookings():
    if current_user.is_admin():
        all_bookings = Booking.query.order_by(Booking.created_at.desc()).all()
        return render_template('bookings/all_bookings.html', bookings=all_bookings)
    from datetime import date as _date
    my_bookings = Booking.query.filter_by(user_id=current_user.id)\
                      .order_by(Booking.created_at.desc()).all()
    return render_template('bookings/my_bookings.html',
                           bookings=my_bookings, today_date=_date.today())


@bookings.route('/bookings/create', methods=['GET', 'POST'])
@login_required
def create_booking():
    if current_user.is_external():
        flash('External members must book via the cart. Browse facilities and click Add to Cart.', 'info')
        return redirect(url_for('facilities.list_facilities'))

    all_facilities = Facility.query.filter_by(is_available=True).all()

    if request.method == 'POST':
        facility_id  = request.form.get('facility_id')
        title        = request.form.get('title', '').strip()
        reason       = request.form.get('reason', '').strip()
        bdate_str    = request.form.get('booking_date', '')
        stime_str    = request.form.get('start_time', '')
        etime_str    = request.form.get('end_time', '')
        attendees    = request.form.get('attendees', 1)
        is_draft     = request.form.get('save_draft') == '1'
        is_recurring = request.form.get('is_recurring') == '1'
        rec_pattern  = request.form.get('recurrence_pattern', 'weekly')
        rec_end_str  = request.form.get('recurrence_end_date', '')

        if not all([facility_id, title, reason, bdate_str, stime_str, etime_str]):
            flash('All fields are required.', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        try:
            booking_date = datetime.strptime(bdate_str, '%Y-%m-%d').date()
            start_time   = datetime.strptime(stime_str, '%H:%M').time()
            end_time     = datetime.strptime(etime_str, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        if booking_date < date.today():
            flash('Booking date cannot be in the past.', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        facility = Facility.query.get(facility_id)
        if not facility:
            flash('Facility not found.', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        if int(attendees) > facility.capacity:
            flash(f'Attendees ({attendees}) exceed facility capacity ({facility.capacity}).', 'danger')
            return render_template('bookings/create.html', facilities=all_facilities)

        rec_end = None
        if is_recurring and rec_end_str:
            try:
                rec_end = datetime.strptime(rec_end_str, '%Y-%m-%d').date()
                if rec_end <= booking_date:
                    flash('Recurrence end date must be after the booking date.', 'danger')
                    return render_template('bookings/create.html', facilities=all_facilities)
            except ValueError:
                flash('Invalid recurrence end date.', 'danger')
                return render_template('bookings/create.html', facilities=all_facilities)

        # Recurring booking 
        if is_recurring and rec_end and not is_draft:
            delta_map = {'daily': 1, 'weekly': 7, 'biweekly': 14}
            delta, dates, current = timedelta(days=delta_map.get(rec_pattern, 7)), [], booking_date
            while current <= rec_end:
                dates.append(current); current += delta

            conflict_dates = [str(d) for d in dates
                              if Booking.check_conflict(facility_id, d, start_time, end_time)]
            if conflict_dates:
                flash(f'Conflicts found on: {", ".join(conflict_dates)}.', 'danger')
                return render_template('bookings/create.html', facilities=all_facilities)

            max_group = db.session.query(db.func.max(Booking.recurrence_group_id)).scalar() or 0
            group_id  = max_group + 1
            created   = []
            for d in dates:
                b = Booking(user_id=current_user.id, facility_id=int(facility_id),
                            title=title, reason=reason, booking_date=d,
                            start_time=start_time, end_time=end_time,
                            attendees=int(attendees), status='pending',
                            is_recurring=True, recurrence_pattern=rec_pattern,
                            recurrence_end_date=rec_end, recurrence_group_id=group_id)
                db.session.add(b); created.append(b)
            db.session.commit()

            for b in created:
                _notify_admins(b)
                try: send_booking_confirmation(b)
                except Exception: pass

            flash(f'Recurring booking submitted for {len(created)} dates!', 'success')
            return redirect(url_for('bookings.list_bookings'))

        # Single booking 
        if not is_draft:
            if Booking.check_conflict(facility_id, booking_date, start_time, end_time):
                flash('This facility is already booked during that time slot.', 'danger')
                return render_template('bookings/create.html', facilities=all_facilities)

        status  = 'draft' if is_draft else 'pending'
        booking = Booking(user_id=current_user.id, facility_id=int(facility_id),
                          title=title, reason=reason, booking_date=booking_date,
                          start_time=start_time, end_time=end_time,
                          attendees=int(attendees), status=status,
                          is_recurring=is_recurring,
                          recurrence_pattern=rec_pattern if is_recurring else None,
                          recurrence_end_date=rec_end)
        db.session.add(booking); db.session.commit()

        if not is_draft:
            _notify_admins(booking)
            try: send_booking_confirmation(booking)
            except Exception: pass
            flash('Booking submitted! Awaiting admin approval.', 'success')
        else:
            flash('Booking saved as draft.', 'info')

        return redirect(url_for('bookings.list_bookings'))

    return render_template('bookings/create.html', facilities=all_facilities)


@bookings.route('/bookings/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_admin() and booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    can_rate = False; existing_rating = None
    if (booking.status == 'approved' and booking.user_id == current_user.id
            and booking.booking_date < date.today()):
        existing_rating = FacilityRating.query.filter_by(
            booking_id=booking.id, user_id=current_user.id).first()
        can_rate = existing_rating is None

    return render_template('bookings/booking_detail.html',
        booking=booking, can_rate=can_rate, existing_rating=existing_rating,
        today=date.today())


# PDF confirmation 
@bookings.route('/bookings/<int:booking_id>/confirmation')
@login_required
def booking_confirmation(booking_id):
    """Printable A4 HTML confirmation page — user prints to PDF from browser."""
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_admin() and booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))
    base_url = request.host_url.rstrip('/')
    return generate_confirmation_html(booking, base_url=base_url)


@bookings.route('/bookings/<int:booking_id>/qr.png')
@login_required
def qr_image(booking_id):
    """Serve QR code PNG for display on booking detail page."""
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_admin() and booking.user_id != current_user.id:
        from flask import abort; abort(403)
    if not booking.qr_token:
        from flask import abort; abort(404)
    from utils.qr_generator import generate_qr_png
    from flask import Response
    qr_url  = f"{request.host_url.rstrip('/')}/checkin/{booking.qr_token}"
    png     = generate_qr_png(qr_url, box_size=8)
    return Response(png, mimetype='image/png')


@bookings.route('/bookings/<int:booking_id>/download-pdf')
@login_required
def download_pdf(booking_id):
    """Download PDF directly (requires weasyprint), else redirect to print page."""
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_admin() and booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    pdf_bytes = try_generate_pdf_bytes(booking)
    if pdf_bytes:
        return Response(pdf_bytes, mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=booking_{booking.id:05d}.pdf'})

    flash('Tip: use File → Print → Save as PDF in your browser.', 'info')
    return redirect(url_for('bookings.booking_confirmation', booking_id=booking_id))


@bookings.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_admin() and booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    cancel_series = request.form.get('cancel_series') == '1'

    if booking.status in ['pending', 'approved', 'draft']:
        if cancel_series and booking.recurrence_group_id:
            series = Booking.query.filter(
                Booking.recurrence_group_id == booking.recurrence_group_id,
                Booking.status.in_(['pending', 'approved']),
                Booking.booking_date >= date.today()).all()
            for b in series:
                b.status = 'cancelled'
                db.session.add(Notification(user_id=b.user_id,
                    message=f'Recurring booking "{b.title}" on {b.booking_date} cancelled.',
                    type='warning', booking_id=b.id))
                try: send_booking_cancelled(b)
                except Exception: pass
            db.session.commit()
            flash(f'Cancelled {len(series)} bookings in this series.', 'info')
        else:
            booking.status = 'cancelled'
            db.session.add(Notification(user_id=booking.user_id,
                message=f'Your booking "{booking.title}" has been cancelled.',
                type='warning', booking_id=booking.id))
            db.session.commit()
            try: send_booking_cancelled(booking)
            except Exception: pass
            flash('Booking cancelled.', 'info')
    else:
        flash('This booking cannot be cancelled.', 'danger')

    return redirect(url_for('bookings.list_bookings'))


@bookings.route('/bookings/<int:booking_id>/submit', methods=['POST'])
@login_required
def submit_draft(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    if booking.status == 'draft':
        if Booking.check_conflict(booking.facility_id, booking.booking_date,
                                   booking.start_time, booking.end_time, exclude_id=booking.id):
            flash('Cannot submit: time slot conflict detected.', 'danger')
            return redirect(url_for('bookings.booking_detail', booking_id=booking.id))
        booking.status = 'pending'; db.session.commit()
        _notify_admins(booking)
        try: send_booking_confirmation(booking)
        except Exception: pass
        flash('Draft submitted for approval.', 'success')

    return redirect(url_for('bookings.list_bookings'))


@bookings.route('/bookings/<int:booking_id>/rate', methods=['POST'])
@login_required
def rate_facility(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    rating_val = request.form.get('rating')
    comment    = request.form.get('comment', '').strip()

    if not rating_val or not rating_val.isdigit() or not (1 <= int(rating_val) <= 5):
        flash('Please provide a valid rating (1–5).', 'danger')
        return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    if FacilityRating.query.filter_by(booking_id=booking.id, user_id=current_user.id).first():
        flash('You have already rated this booking.', 'warning')
        return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    db.session.add(FacilityRating(facility_id=booking.facility_id, user_id=current_user.id,
        booking_id=booking.id, rating=int(rating_val), comment=comment or None))
    db.session.commit()
    flash('Thank you for your rating!', 'success')
    return redirect(url_for('bookings.booking_detail', booking_id=booking.id))


@bookings.route('/calendar')
@login_required
def calendar_view():
    all_facilities = Facility.query.filter_by(is_available=True).order_by(Facility.name).all()
    return render_template('bookings/calendar.html', facilities=all_facilities)


@bookings.route('/api/calendar-events')
@login_required
def calendar_events():
    facility_id = request.args.get('facility_id')
    start_str   = request.args.get('start', '')
    end_str     = request.args.get('end', '')
    query = Booking.query.filter(Booking.status.in_(['approved', 'paid']))
    if facility_id:
        query = query.filter(Booking.facility_id == int(facility_id))
    try:
        if start_str: query = query.filter(Booking.booking_date >= datetime.fromisoformat(start_str[:10]).date())
        if end_str:   query = query.filter(Booking.booking_date <= datetime.fromisoformat(end_str[:10]).date())
    except (ValueError, TypeError): pass

    color_map = {'lab': '#2563a8', 'hall': '#e8a020', 'sports': '#28a745', 'lecture_room': '#dc3545'}
    return jsonify([{
        'id': b.id, 'title': f"{b.facility.name}: {b.title}",
        'start': f"{b.booking_date}T{b.start_time.strftime('%H:%M:%S')}",
        'end':   f"{b.booking_date}T{b.end_time.strftime('%H:%M:%S')}",
        'color': color_map.get(b.facility.facility_type, '#6c757d'),
        'extendedProps': {'facility': b.facility.name, 'bookedBy': b.user.full_name,
            'attendees': b.attendees, 'bookingId': b.id, 'isRecurring': b.is_recurring}
    } for b in query.all()])


@bookings.route('/api/availability')
@login_required
def check_availability():
    facility_id  = request.args.get('facility_id')
    booking_date = request.args.get('date')
    if not facility_id or not booking_date: return jsonify({'bookings': []})
    try: d = datetime.strptime(booking_date, '%Y-%m-%d').date()
    except ValueError: return jsonify({'bookings': []})
    day_bookings = Booking.query.filter(
        Booking.facility_id == facility_id,
        Booking.booking_date == d,
        Booking.status.in_(['approved', 'paid'])
    ).all()
    return jsonify({'bookings': [
        {'title': b.title, 'start': b.start_time.strftime('%H:%M'),
         'end': b.end_time.strftime('%H:%M')} for b in day_bookings]})


@bookings.route('/bookings/<int:booking_id>/reschedule', methods=['GET', 'POST'])
@login_required
def reschedule_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    # Access control
    if booking.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('bookings.list_bookings'))

    # Eligibility rules
    # Internal (student/staff): must be approved or pending, not yet attended
    # External: must be paid, booking date must be in the future, not yet attended
    if current_user.is_external():
        if booking.status != 'paid':
            flash('Only confirmed paid bookings can be rescheduled.', 'warning')
            return redirect(url_for('bookings.booking_detail', booking_id=booking.id))
    else:
        if booking.status not in ['approved', 'pending']:
            flash('Only approved or pending bookings can be rescheduled.', 'warning')
            return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    if booking.booking_date <= date.today():
        flash('Only future bookings can be rescheduled.', 'warning')
        return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    if booking.is_attended:
        flash('Attended bookings cannot be rescheduled.', 'warning')
        return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    if request.method == 'POST':
        new_date_str  = request.form.get('booking_date', '').strip()
        new_start_str = request.form.get('start_time', '').strip()
        new_end_str   = request.form.get('end_time', '').strip()

        if not all([new_date_str, new_start_str, new_end_str]):
            flash('Date, start time and end time are all required.', 'danger')
            return render_template('bookings/reschedule.html', booking=booking)

        try:
            new_date  = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_start = datetime.strptime(new_start_str, '%H:%M').time()
            new_end   = datetime.strptime(new_end_str, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return render_template('bookings/reschedule.html', booking=booking)

        if new_date <= date.today():
            flash('New booking date must be in the future.', 'danger')
            return render_template('bookings/reschedule.html', booking=booking)

        if new_start >= new_end:
            flash('End time must be after start time.', 'danger')
            return render_template('bookings/reschedule.html', booking=booking)

        # Check no conflict on the new date/time (exclude current booking)
        if Booking.check_conflict(booking.facility_id, new_date, new_start, new_end,
                                   exclude_id=booking.id):
            flash('That time slot is already booked for this facility. Please choose another.', 'danger')
            return render_template('bookings/reschedule.html', booking=booking)

        # Save old values for the email
        old_date  = booking.booking_date
        old_start = booking.start_time
        old_end   = booking.end_time

        # Apply changes
        booking.booking_date  = new_date
        booking.start_time    = new_start
        booking.end_time      = new_end
        booking.reminder_sent = False   # reset so reminder fires at new time

        db.session.add(Notification(
            user_id    = booking.user_id,
            message    = (f'Your booking "{booking.title}" has been rescheduled to '
                          f'{new_date.strftime("%d %b %Y")} at '
                          f'{new_start.strftime("%H:%M")} – {new_end.strftime("%H:%M")}.'),
            type       = 'info',
            booking_id = booking.id,
        ))
        db.session.commit()

        try: send_booking_rescheduled(booking, old_date, old_start, old_end)
        except Exception: pass

        flash('Booking rescheduled successfully! A confirmation email has been sent.', 'success')
        return redirect(url_for('bookings.booking_detail', booking_id=booking.id))

    return render_template('bookings/reschedule.html', booking=booking)


def _notify_admins(booking):
    from models import User
    admins = User.query.filter_by(role='admin').all()
    for a in admins:
        db.session.add(Notification(user_id=a.id,
            message=f'New booking: "{booking.title}" by {booking.user.full_name} '
                    f'for {booking.facility.name} on {booking.booking_date}.',
            type='info', booking_id=booking.id))
        try: send_admin_new_request(booking, a.email)
        except Exception: pass
    db.session.commit()
