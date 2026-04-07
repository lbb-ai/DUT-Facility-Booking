from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Booking, Facility, User, FacilityRating
from datetime import date, timedelta
from collections import defaultdict
from functools import wraps

analytics = Blueprint('analytics', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@analytics.route('/admin/analytics')
@login_required
@admin_required
def reports():
    today          = date.today()
    last_30        = today - timedelta(days=30)
    last_90        = today - timedelta(days=90)

    # KPIs 
    total_bookings  = Booking.query.count()
    total_approved  = Booking.query.filter_by(status='approved').count()
    total_rejected  = Booking.query.filter_by(status='rejected').count()
    total_pending   = Booking.query.filter_by(status='pending').count()
    total_cancelled = Booking.query.filter_by(status='cancelled').count()
    total_users     = User.query.count()
    total_facilities = Facility.query.count()
    approval_rate   = round((total_approved / total_bookings * 100) if total_bookings else 0, 1)

    avg_rating_row = db.session.query(db.func.avg(FacilityRating.rating)).scalar()
    avg_overall_rating = round(avg_rating_row, 1) if avg_rating_row else None

    # Daily bookings last 30 days 
    recent = Booking.query.filter(Booking.booking_date >= last_30).all()
    daily  = defaultdict(lambda: {'total': 0, 'approved': 0})
    for b in recent:
        k = str(b.booking_date)
        daily[k]['total'] += 1
        if b.status == 'approved':
            daily[k]['approved'] += 1

    chart_daily_labels, chart_daily_total, chart_daily_approved = [], [], []
    for i in range(30):
        d = last_30 + timedelta(days=i)
        k = str(d)
        chart_daily_labels.append(d.strftime('%d %b'))
        chart_daily_total.append(daily[k]['total'])
        chart_daily_approved.append(daily[k]['approved'])

    # Status breakdown 
    status_labels  = ['Approved', 'Pending', 'Rejected', 'Cancelled', 'Draft']
    status_values  = [total_approved, total_pending, total_rejected, total_cancelled,
                      Booking.query.filter_by(status='draft').count()]
    status_colours = ['#28a745', '#e8a020', '#dc3545', '#6c757d', '#17a2b8']

    # Peak hours (last 90 days)
    hour_counts = defaultdict(int)
    for b in Booking.query.filter_by(status='approved')\
                    .filter(Booking.booking_date >= last_90).all():
        hour_counts[b.start_time.hour] += 1
    peak_labels = [f"{h:02d}:00" for h in range(7, 22)]
    peak_values = [hour_counts.get(h, 0) for h in range(7, 22)]

    # Day of week (last 90 days) 
    dow_counts = defaultdict(int)
    for b in Booking.query.filter_by(status='approved')\
                    .filter(Booking.booking_date >= last_90).all():
        dow_counts[b.booking_date.weekday()] += 1
    dow_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    dow_values = [dow_counts.get(i, 0) for i in range(7)]

    # Facility type breakdown 
    type_counts = defaultdict(int)
    for b in Booking.query.filter_by(status='approved').all():
        type_counts[b.facility.facility_type] += 1
    type_labels = [t.replace('_', ' ').title() for t in type_counts.keys()]
    type_values = list(type_counts.values())

    # Facility utilisation (last 90 days)
    facility_stats = []
    for f in Facility.query.all():
        approved = Booking.query.filter_by(facility_id=f.id, status='approved')\
                       .filter(Booking.booking_date >= last_90).all()
        hours = sum(b.duration_hours for b in approved)
        facility_stats.append({
            'name': f.name, 'type': f.facility_type,
            'bookings': len(approved), 'hours': round(hours, 1),
            'avg_rating': f.avg_rating, 'rating_count': f.rating_count
        })
    facility_stats.sort(key=lambda x: x['bookings'], reverse=True)

    # Top users 
    top_users = db.session.query(
        User.name, User.surname, User.student_number, User.role,
        db.func.count(Booking.id).label('cnt')
    ).join(Booking, Booking.user_id == User.id)\
     .filter(Booking.status == 'approved')\
     .group_by(User.id)\
     .order_by(db.func.count(Booking.id).desc())\
     .limit(8).all()

    # Recent reviews 
    recent_ratings = FacilityRating.query\
                         .order_by(FacilityRating.created_at.desc()).limit(8).all()

    return render_template('admin/analytics.html',
        # KPIs
        total_bookings=total_bookings, total_approved=total_approved,
        total_rejected=total_rejected, total_pending=total_pending,
        total_cancelled=total_cancelled, total_users=total_users,
        total_facilities=total_facilities, approval_rate=approval_rate,
        avg_overall_rating=avg_overall_rating,
        # Charts
        chart_daily_labels=chart_daily_labels,
        chart_daily_total=chart_daily_total,
        chart_daily_approved=chart_daily_approved,
        status_labels=status_labels, status_values=status_values, status_colours=status_colours,
        peak_labels=peak_labels, peak_values=peak_values,
        dow_labels=dow_labels, dow_values=dow_values,
        type_labels=type_labels, type_values=type_values,
        # Tables
        facility_stats=facility_stats,
        top_users=top_users,
        recent_ratings=recent_ratings,
    )
