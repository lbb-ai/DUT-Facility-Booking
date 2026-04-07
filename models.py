from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets, uuid


# User 
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id                   = db.Column(db.Integer,     primary_key=True)
    student_number       = db.Column(db.String(20),  unique=True, nullable=True)   # nullable for external
    name                 = db.Column(db.String(100), nullable=False)
    surname              = db.Column(db.String(100), nullable=False)
    email                = db.Column(db.String(150), unique=True, nullable=False)
    password_hash        = db.Column(db.String(256), nullable=True)
    role                 = db.Column(db.String(20),  nullable=False, default='student')
    is_active            = db.Column(db.Boolean,     default=True)
    created_at           = db.Column(db.DateTime,    default=datetime.utcnow)

    # Profile 
    profile_picture      = db.Column(db.String(300), nullable=True)
    bio                  = db.Column(db.String(500), nullable=True)
    phone                = db.Column(db.String(30),  nullable=True)
    organisation         = db.Column(db.String(200), nullable=True)   # for external users

    #  Password reset 
    reset_token          = db.Column(db.String(100), nullable=True, unique=True)
    reset_token_expiry   = db.Column(db.DateTime,    nullable=True)

    # OAuth 
    oauth_provider       = db.Column(db.String(30),  nullable=True)
    oauth_id             = db.Column(db.String(200), nullable=True, unique=True)

    bookings        = db.relationship('Booking',        foreign_keys='Booking.user_id',        backref='user', lazy='dynamic')
    notifications   = db.relationship('Notification',   foreign_keys='Notification.user_id',   backref='user', lazy='dynamic')
    ratings         = db.relationship('FacilityRating', foreign_keys='FacilityRating.user_id', backref='user', lazy='dynamic')
    payment_orders  = db.relationship('PaymentOrder',   foreign_keys='PaymentOrder.user_id',   backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.name} {self.surname}"

    def is_admin(self):
        return self.role == 'admin'

    def is_staff(self):
        return self.role in ['staff', 'admin']

    def is_external(self):
        return self.role == 'external'

    def is_oauth_user(self):
        return self.oauth_provider is not None

    def generate_reset_token(self):
        self.reset_token        = secrets.token_urlsafe(48)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def verify_reset_token(self, token):
        if self.reset_token != token:
            return False
        if not self.reset_token_expiry or datetime.utcnow() > self.reset_token_expiry:
            return False
        return True

    def clear_reset_token(self):
        self.reset_token        = None
        self.reset_token_expiry = None

    @property
    def avatar_url(self):
        if self.profile_picture:
            return f'/static/uploads/avatars/{self.profile_picture}'
        initials = f"{self.name[0]}{self.surname[0]}".upper()
        return f'https://ui-avatars.com/api/?name={initials}&background=1a3a5c&color=fff&size=128&font-size=0.45&bold=true'

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Facility 
class Facility(db.Model):
    __tablename__ = 'facilities'
    id               = db.Column(db.Integer,     primary_key=True)
    name             = db.Column(db.String(150), nullable=False)
    facility_type    = db.Column(db.String(50),  nullable=False)
    location         = db.Column(db.String(200), nullable=False)
    capacity         = db.Column(db.Integer,     nullable=False)
    description      = db.Column(db.Text)
    equipment        = db.Column(db.Text)
    campus           = db.Column(db.String(100), nullable=True)
    is_available     = db.Column(db.Boolean,     default=True)
    image_filename   = db.Column(db.String(300), nullable=True)
    # External booking 
    allow_external   = db.Column(db.Boolean,     default=False)
    price_per_hour   = db.Column(db.Numeric(10,2), nullable=True)  # ZAR; NULL = not bookable externally
    created_at       = db.Column(db.DateTime,    default=datetime.utcnow)

    bookings  = db.relationship('Booking',        backref='facility', lazy='dynamic')
    ratings   = db.relationship('FacilityRating', backref='facility', lazy='dynamic')

    DUT_CAMPUSES = [
        'Indumiso', 'Ritson', 'ML Sultan', 'Riverside',
        'Brickfield', 'City Campus', 'Steve Biko'
    ]

    @property
    def equipment_list(self):
        if self.equipment:
            return [e.strip() for e in self.equipment.split(',')]
        return []

    @property
    def image_url(self):
        if self.image_filename:
            return f'/static/uploads/facilities/{self.image_filename}'
        return None

    @property
    def avg_rating(self):
        all_ratings = FacilityRating.query.filter_by(facility_id=self.id).all()
        if not all_ratings:
            return None
        return round(sum(r.rating for r in all_ratings) / len(all_ratings), 1)

    @property
    def rating_count(self):
        return FacilityRating.query.filter_by(facility_id=self.id).count()

    def price_for_hours(self, hours):
        if self.price_per_hour is None:
            return 0
        return float(self.price_per_hour) * hours

    def __repr__(self):
        return f'<Facility {self.name}>'


# Booking 
class Booking(db.Model):
    __tablename__ = 'bookings'
    id                   = db.Column(db.Integer,  primary_key=True)
    user_id              = db.Column(db.Integer,  db.ForeignKey('users.id'),      nullable=False)
    facility_id          = db.Column(db.Integer,  db.ForeignKey('facilities.id'), nullable=False)
    title                = db.Column(db.String(200), nullable=False)
    reason               = db.Column(db.Text,        nullable=False)
    booking_date         = db.Column(db.Date,        nullable=False)
    start_time           = db.Column(db.Time,        nullable=False)
    end_time             = db.Column(db.Time,        nullable=False)
    attendees            = db.Column(db.Integer,  default=1)
    status               = db.Column(db.String(20),  default='pending')
    admin_notes          = db.Column(db.Text)
    is_recurring         = db.Column(db.Boolean,  default=False)
    recurrence_pattern   = db.Column(db.String(20))
    recurrence_end_date  = db.Column(db.Date)
    recurrence_group_id  = db.Column(db.Integer)
    # External payment linkage 
    payment_order_id     = db.Column(db.Integer,  db.ForeignKey('payment_orders.id'), nullable=True)
    amount_paid          = db.Column(db.Numeric(10,2), nullable=True)
    # QR Check-in 
    qr_token             = db.Column(db.String(200), unique=True, nullable=True)
    attended_at          = db.Column(db.DateTime,    nullable=True)
    attended_by_id       = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=True)
    reminder_sent        = db.Column(db.Boolean,     default=False)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ratings      = db.relationship('FacilityRating', backref='booking', lazy='dynamic')
    attended_by  = db.relationship('User', foreign_keys=[attended_by_id], lazy='select')

    @staticmethod
    def check_conflict(facility_id, booking_date, start_time, end_time, exclude_id=None):
        query = Booking.query.filter(
            Booking.facility_id  == facility_id,
            Booking.booking_date == booking_date,
            Booking.status.in_(['approved', 'paid']),
            Booking.start_time   <  end_time,
            Booking.end_time     >  start_time,
        )
        if exclude_id:
            query = query.filter(Booking.id != exclude_id)
        return query.all()

    @property
    def duration_hours(self):
        start = datetime.combine(self.booking_date, self.start_time)
        end   = datetime.combine(self.booking_date, self.end_time)
        return (end - start).seconds / 3600

    def generate_recurring_dates(self):
        if not self.is_recurring or not self.recurrence_end_date:
            return [self.booking_date]
        delta_map = {'daily': 1, 'weekly': 7, 'biweekly': 14}
        delta = timedelta(days=delta_map.get(self.recurrence_pattern, 7))
        dates, current = [], self.booking_date
        while current <= self.recurrence_end_date:
            dates.append(current); current += delta
        return dates

    def generate_qr_token(self):
        import secrets as _sec
        self.qr_token = f"DUTFBS-{self.id}-{_sec.token_urlsafe(24)}"
        return self.qr_token

    @property
    def is_attended(self):
        return self.attended_at is not None

    @property
    def checkin_url(self):
        if self.qr_token:
            return f"/checkin/{self.qr_token}"
        return None

    def __repr__(self):
        return f'<Booking {self.id} [{self.status}]>'


# Notification 
class Notification(db.Model):
    __tablename__ = 'notifications'
    id         = db.Column(db.Integer,    primary_key=True)
    user_id    = db.Column(db.Integer,    db.ForeignKey('users.id'), nullable=False)
    message    = db.Column(db.Text,       nullable=False)
    type       = db.Column(db.String(30), default='info')
    is_read    = db.Column(db.Boolean,    default=False)
    booking_id = db.Column(db.Integer,    db.ForeignKey('bookings.id'), nullable=True)
    created_at = db.Column(db.DateTime,   default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id}>'


# FacilityRating 
class FacilityRating(db.Model):
    __tablename__ = 'facility_ratings'
    id          = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),      nullable=False)
    booking_id  = db.Column(db.Integer, db.ForeignKey('bookings.id'),   nullable=True)   # nullable for standalone reviews
    rating      = db.Column(db.Integer, nullable=False)
    comment     = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<FacilityRating {self.rating}★>'


# PaymentOrder 
class PaymentOrder(db.Model):
    __tablename__ = 'payment_orders'
    id               = db.Column(db.Integer,     primary_key=True)
    user_id          = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=False)
    reference        = db.Column(db.String(64),  unique=True, nullable=False)   # UUID sent to PayFast
    amount_total     = db.Column(db.Numeric(10,2), nullable=False)
    status           = db.Column(db.String(20),  default='pending')  # pending/paid/failed/cancelled
    payfast_pf_payment_id = db.Column(db.String(100), nullable=True)
    created_at       = db.Column(db.DateTime,    default=datetime.utcnow)
    paid_at          = db.Column(db.DateTime,    nullable=True)

    line_items = db.relationship('BookingLineItem', backref='order', lazy='dynamic',
                                  cascade='all, delete-orphan')
    bookings   = db.relationship('Booking',         backref='payment_order',
                                  foreign_keys='Booking.payment_order_id', lazy='dynamic')

    @staticmethod
    def generate_reference():
        return f"DUTFBS-{uuid.uuid4().hex[:12].upper()}"

    def __repr__(self):
        return f'<PaymentOrder {self.reference} [{self.status}]>'


# BookingLineItem 
class BookingLineItem(db.Model):
    __tablename__ = 'booking_line_items'
    id               = db.Column(db.Integer, primary_key=True)
    payment_order_id = db.Column(db.Integer, db.ForeignKey('payment_orders.id'), nullable=False)
    facility_id      = db.Column(db.Integer, db.ForeignKey('facilities.id'),     nullable=False)
    title            = db.Column(db.String(200), nullable=False)
    reason           = db.Column(db.Text,        nullable=False)
    booking_date     = db.Column(db.Date,        nullable=False)
    start_time       = db.Column(db.Time,        nullable=False)
    end_time         = db.Column(db.Time,        nullable=False)
    attendees        = db.Column(db.Integer,     default=1)
    price            = db.Column(db.Numeric(10,2), nullable=False)  # calculated at add-to-cart
    booking_id       = db.Column(db.Integer,     db.ForeignKey('bookings.id'), nullable=True)

    facility = db.relationship('Facility')

    @property
    def duration_hours(self):
        start = datetime.combine(self.booking_date, self.start_time)
        end   = datetime.combine(self.booking_date, self.end_time)
        return (end - start).seconds / 3600

    def __repr__(self):
        return f'<LineItem {self.facility_id} {self.booking_date}>'
