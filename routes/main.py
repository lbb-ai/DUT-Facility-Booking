from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models import Booking, Facility, Notification
from datetime import date

main = Blueprint('main', __name__)


@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        total_bookings  = Booking.query.count()
        pending_count   = Booking.query.filter_by(status='pending').count()
        total_facilities = Facility.query.count()
        todays_bookings = Booking.query.filter_by(
            booking_date=date.today(), status='approved').all()
        recent_bookings = Booking.query.order_by(
            Booking.created_at.desc()).limit(10).all()
        return render_template('admin/dashboard.html',
            total_bookings=total_bookings,
            pending_count=pending_count,
            total_facilities=total_facilities,
            todays_bookings=todays_bookings,
            recent_bookings=recent_bookings)

    # Regular user dashboard
    my_bookings  = Booking.query.filter_by(user_id=current_user.id)\
                       .order_by(Booking.created_at.desc()).limit(5).all()
    upcoming     = Booking.query.filter(
                       Booking.user_id      == current_user.id,
                       Booking.status       == 'approved',
                       Booking.booking_date >= date.today()
                   ).order_by(Booking.booking_date).limit(5).all()
    pending_mine = Booking.query.filter_by(
                       user_id=current_user.id, status='pending').count()

    return render_template('bookings/dashboard.html',
        my_bookings=my_bookings,
        upcoming=upcoming,
        pending_mine=pending_mine)
