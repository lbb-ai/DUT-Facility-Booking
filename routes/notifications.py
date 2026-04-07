from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Notification

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/notifications')
@login_required
def list_notifications():
    all_notifs = Notification.query\
        .filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    # Mark all as read
    for n in all_notifs:
        n.is_read = True
    db.session.commit()
    return render_template('notifications/list.html', notifications=all_notifs)


@notifications_bp.route('/notifications/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})
