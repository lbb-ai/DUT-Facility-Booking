"""
Payments blueprint — PayFast redirect flow.
  /payments/checkout  → validate cart, create PaymentOrder, redirect to PayFast
  /payments/success   → PayFast return_url (mark paid, create bookings)
  /payments/cancelled → PayFast cancel_url
  /payments/failed    → manual failed landing
  /payments/notify    → passive ITN handler (logs only — not relied on for confirmation)
"""
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app)
from flask_login import login_required, current_user
from extensions import db
from models import Facility, Booking, PaymentOrder, BookingLineItem, Notification
from utils.payfast import build_payfast_form
from routes.cart import get_cart, save_cart, external_required, cart_total, CART_KEY
from datetime import datetime, date
from decimal import Decimal

payments = Blueprint('payments', __name__, url_prefix='/payments')


# Checkout - validate cart → create order → redirect 
@payments.route('/checkout', methods=['POST'])
@login_required
@external_required
def checkout():
    items = get_cart()
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart.view_cart'))

    # Validate all items are still conflict-free
    errors = []
    for i, item in enumerate(items):
        try:
            bd = datetime.strptime(item['booking_date'], '%Y-%m-%d').date()
            st = datetime.strptime(item['start_time'], '%H:%M').time()
            et = datetime.strptime(item['end_time'],   '%H:%M').time()
        except ValueError:
            errors.append(f"Item {i+1} has invalid date/time.")
            continue
        if bd < date.today():
            errors.append(f"Booking date for \"{item['facility_name']}\" is in the past.")
            continue
        facility = Facility.query.get(item['facility_id'])
        if not facility or not facility.allow_external or not facility.is_available:
            errors.append(f"\"{item['facility_name']}\" is no longer available.")
            continue
        if Booking.check_conflict(item['facility_id'], bd, st, et):
            errors.append(f"\"{item['facility_name']}\" on {item['booking_date']} now has a conflict.")

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('cart.view_cart'))

    total = Decimal(str(round(cart_total(items), 2)))

    # Create PaymentOrder + line items
    order = PaymentOrder(
        user_id      = current_user.id,
        reference    = PaymentOrder.generate_reference(),
        amount_total = total,
        status       = 'pending',
    )
    db.session.add(order)
    db.session.flush()  # get order.id

    for item in items:
        bd = datetime.strptime(item['booking_date'], '%Y-%m-%d').date()
        st = datetime.strptime(item['start_time'],   '%H:%M').time()
        et = datetime.strptime(item['end_time'],     '%H:%M').time()
        li = BookingLineItem(
            payment_order_id = order.id,
            facility_id      = item['facility_id'],
            title            = item['title'],
            reason           = item['reason'],
            booking_date     = bd,
            start_time       = st,
            end_time         = et,
            attendees        = item['attendees'],
            price            = Decimal(str(item['price'])),
        )
        db.session.add(li)

    db.session.commit()

    # Store order reference in session for success handler
    session['pending_order_ref'] = order.reference

    # Build PayFast form
    pf = build_payfast_form(
        order      = order,
        user       = current_user,
        return_url = url_for('payments.success',   _external=True),
        cancel_url = url_for('payments.cancelled', _external=True),
    )

    # Auto-submit POST form via rendered page
    return render_template('payments/redirect.html', pf=pf)


# Success Page
@payments.route('/success')
@login_required
@external_required
def success():
    ref   = session.pop('pending_order_ref', None)
    order = None

    if ref:
        order = PaymentOrder.query.filter_by(
            reference=ref, user_id=current_user.id).first()

    if not order:
        # Try latest pending order for this user as fallback
        order = PaymentOrder.query.filter_by(
            user_id=current_user.id, status='pending'
        ).order_by(PaymentOrder.created_at.desc()).first()

    if not order:
        flash('Could not find your payment order. Contact support.', 'warning')
        return redirect(url_for('main.dashboard'))

    if order.status == 'paid':
        # Already processed (page reload)
        bookings = list(order.bookings)
        return render_template('payments/success.html', order=order, bookings=bookings)

    # Mark paid and create actual bookings
    order.status  = 'paid'
    order.paid_at = datetime.utcnow()

    created_bookings = []
    for li in order.line_items:
        booking = Booking(
            user_id          = current_user.id,
            facility_id      = li.facility_id,
            title            = li.title,
            reason           = li.reason,
            booking_date     = li.booking_date,
            start_time       = li.start_time,
            end_time         = li.end_time,
            attendees        = li.attendees,
            status           = 'paid',
            payment_order_id = order.id,
            amount_paid      = li.price,
        )
        db.session.add(booking)
        db.session.flush()
        booking.generate_qr_token()
        li.booking_id = booking.id
        created_bookings.append(booking)

        # Notify admins
        from models import User
        for admin in User.query.filter_by(role='admin').all():
            db.session.add(Notification(
                user_id    = admin.id,
                message    = f'External booking PAID: "{li.title}" for {li.facility.name} '
                             f'on {li.booking_date} by {current_user.full_name}.',
                type       = 'success',
                booking_id = booking.id,
            ))

    db.session.commit()

    # Send confirmation email with PDF to each booking
    for booking in created_bookings:
        try:
            from utils.email_service import send_external_booking_confirmed
            send_external_booking_confirmed(booking)
        except Exception as e:
            current_app.logger.warning(f'External confirmation email failed: {e}')

    # Clear cart
    save_cart([])

    return render_template('payments/success.html', order=order, bookings=created_bookings)


# Cancelled 
@payments.route('/cancelled')
@login_required
@external_required
def cancelled():
    ref   = session.pop('pending_order_ref', None)
    order = None
    if ref:
        order = PaymentOrder.query.filter_by(reference=ref, user_id=current_user.id).first()
    if order and order.status == 'pending':
        order.status = 'cancelled'
        db.session.commit()
    return render_template('payments/cancelled.html', order=order)


# Failed Page
@payments.route('/failed')
@login_required
@external_required
def failed():
    ref   = session.pop('pending_order_ref', None)
    order = None
    if ref:
        order = PaymentOrder.query.filter_by(reference=ref, user_id=current_user.id).first()
    if order and order.status == 'pending':
        order.status = 'failed'
        db.session.commit()
    return render_template('payments/failed.html', order=order)


# Passive ITN notify (log only)
@payments.route('/notify', methods=['POST'])
def notify():
    data = request.form.to_dict()
    ref  = data.get('m_payment_id')
    current_app.logger.info(f'[PayFast ITN] ref={ref} status={data.get("payment_status")}')
    # Passive — redirect-based success handler is the authoritative confirmation
    return 'OK', 200
