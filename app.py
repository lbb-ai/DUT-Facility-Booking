from flask import Flask
from config import config
from extensions import db, login_manager, migrate, csrf, mail


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)

    from routes.auth          import auth
    from routes.main          import main
    from routes.bookings      import bookings
    from routes.facilities    import facilities
    from routes.admin         import admin
    from routes.notifications import notifications_bp
    from routes.analytics     import analytics
    from routes.cart          import cart
    from routes.payments      import payments
    from routes.checkin       import checkin

    # auth blueprint now has url_prefix='/auth' — other routes stay at /
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(bookings)
    app.register_blueprint(facilities)
    app.register_blueprint(admin)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(analytics)
    app.register_blueprint(cart)
    app.register_blueprint(payments)
    app.register_blueprint(checkin)

    app.jinja_env.globals['enumerate'] = enumerate

    with app.app_context():
        db.create_all()
        _seed_data()

    # Start background scheduler — guard against double-start in debug reloader
    import os
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from utils.scheduler import init_scheduler
        init_scheduler(app)

    return app


def _seed_data():
    from models import User, Facility

    if not User.query.filter_by(role='admin').first():
        admin_user = User(
            student_number='ADMIN001',
            name='System', surname='Administrator',
            email='hadebema69@gmail.com', role='admin',
        )
        admin_user.set_password('Admin@1234')
        db.session.add(admin_user)

    if Facility.query.count() == 0:
        sample = [
            Facility(name='Computer Lab A',  facility_type='lab', campus='Steve Biko',
                     location='Block A, Room 101', capacity=30,
                     description='Modern computer lab with 30 workstations.',
                     equipment='30 PCs, Projector, Whiteboard, WiFi',image_url='static/images/PcLabs.jpg'),
            Facility(name='Computer Lab B',  facility_type='lab', campus='ML Sultan',
                     location='Block A, Room 102', capacity=25,
                     description='Programming lab with Linux and Windows systems.',
                     equipment='25 PCs, Dual Monitors, Network Switch',image_url='static/images/comp-lab.jpg'),
            Facility(name='Main Hall', facility_type='hall', campus='Steve Biko',
                     location='Admin Block, Ground Floor', capacity=300,
                     description='Large multipurpose hall for events.',
                     equipment='PA System, Projector, Stage, Chairs',image_url='static/images/main-hall.jpg'),
            Facility(name='Seminar Room 1',  facility_type='hall', campus='Ritson',
                     location='Block B, Room 201', capacity=50,
                     description='Ideal for seminars and group presentations.',
                     equipment='Projector, Whiteboard, Conference Table',image_url='static/images/seminar-room.jpg'),
            Facility(name='Sports Hall',     facility_type='sports', campus='Indumiso',
                     location='Sports Complex', capacity=100,
                     description='Indoor sports hall.',
                     equipment='Basketball Hoops, Volleyball Net, Scoreboards',image_url='static/images/sports-hall.jpg'),
            Facility(name='Soccer Field',    facility_type='sports', campus='Riverside',
                     location='Sports Grounds', capacity=200,
                     description='Full-size soccer field with floodlights.',
                     equipment='Goalposts, Floodlights, Changing Rooms',image_url='static/images/soccer-field.jpg'),
            Facility(name='Lecture Hall 1',  facility_type='lecture_room', campus='City Campus',
                     location='Block C, Room 001', capacity=120,
                     description='Large tiered lecture theatre.',
                     equipment='Projector, Microphone, Recording System',image_url='static/images/lecture-hall.jpg'),
        ]
        for f in sample:
            db.session.add(f)

    db.session.commit()


app = create_app('development')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
