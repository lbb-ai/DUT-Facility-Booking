"""
Cart blueprint — external users only.
Cart is stored in Flask session as a list of dicts.
"""
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, jsonify)
from flask_login import login_required, current_user
from extensions import db
from models import Facility, Booking
from datetime import datetime, date
from functools import wraps

cart = Blueprint('cart', __name__, url_prefix='/cart')

CART_KEY = 'external_cart'


def external_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in as an external member to use the cart.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_external():
            flash('The cart is only available for external members.', 'warning')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


def get_cart():
    return session.get(CART_KEY, [])


def save_cart(items):
    session[CART_KEY] = items
    session.modified  = True


def cart_total(items):
    return sum(float(i['price']) for i in items)


def cart_count():
    return len(session.get(CART_KEY, []))


# View cart 
@cart.route('/')
@login_required
@external_required
def view_cart():
    items = get_cart()
    total = cart_total(items)
    return render_template('cart/cart.html', items=items, total=total)


# Add to cart 
@cart.route('/add', methods=['POST'])
@login_required
@external_required
def add_to_cart():
    facility_id = request.form.get('facility_id', type=int)
    title       = request.form.get('title', '').strip()
    reason      = request.form.get('reason', '').strip()
    bdate_str   = request.form.get('booking_date', '')
    stime_str   = request.form.get('start_time', '')
    etime_str   = request.form.get('end_time', '')
    attendees   = request.form.get('attendees', 1, type=int)

    if not all([facility_id, title, reason, bdate_str, stime_str, etime_str]):
        flash('All booking fields are required.', 'danger')
        return redirect(url_for('facilities.list_facilities'))

    try:
        booking_date = datetime.strptime(bdate_str, '%Y-%m-%d').date()
        start_time   = datetime.strptime(stime_str, '%H:%M').time()
        end_time     = datetime.strptime(etime_str, '%H:%M').time()
    except ValueError:
        flash('Invalid date or time.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    if booking_date < date.today():
        flash('Booking date cannot be in the past.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    if start_time >= end_time:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    facility = Facility.query.get_or_404(facility_id)

    if not facility.allow_external:
        flash('This facility is not available for external bookings.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    if not facility.is_available:
        flash('This facility is currently unavailable.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    if attendees > facility.capacity:
        flash(f'Attendees exceed facility capacity ({facility.capacity}).', 'warning')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    # Conflict check
    conflicts = Booking.check_conflict(facility_id, booking_date, start_time, end_time)
    if conflicts:
        flash('This facility is already booked during that time slot.', 'danger')
        return redirect(url_for('facilities.facility_detail', facility_id=facility_id))

    # Calculate price
    start_dt = datetime.combine(booking_date, start_time)
    end_dt   = datetime.combine(booking_date, end_time)
    hours    = (end_dt - start_dt).seconds / 3600
    price    = round(float(facility.price_per_hour or 0) * hours, 2)

    # Check not already in cart
    items = get_cart()
    for item in items:
        if (item['facility_id'] == facility_id
                and item['booking_date'] == bdate_str
                and item['start_time'] == stime_str):
            flash('This time slot is already in your cart.', 'warning')
            return redirect(url_for('cart.view_cart'))

    items.append({
        'facility_id':   facility_id,
        'facility_name': facility.name,
        'facility_campus': facility.campus or '',
        'title':         title,
        'reason':        reason,
        'booking_date':  bdate_str,
        'start_time':    stime_str,
        'end_time':      etime_str,
        'attendees':     attendees,
        'hours':         round(hours, 2),
        'price':         price,
        'price_per_hour': float(facility.price_per_hour or 0),
    })
    save_cart(items)
    flash(f'"{facility.name}" added to cart! Total: R{cart_total(items):.2f}', 'success')
    return redirect(url_for('cart.view_cart'))


# Remove item 
@cart.route('/remove/<int:index>', methods=['POST'])
@login_required
@external_required
def remove_from_cart(index):
    items = get_cart()
    if 0 <= index < len(items):
        removed = items.pop(index)
        save_cart(items)
        flash(f'"{removed["facility_name"]}" removed from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


# Clear cart
@cart.route('/clear', methods=['POST'])
@login_required
@external_required
def clear_cart():
    save_cart([])
    flash('Cart cleared.', 'info')
    return redirect(url_for('cart.view_cart'))


# Cart count API
@cart.route('/count')
def cart_count_api():
    return jsonify({'count': cart_count()})
