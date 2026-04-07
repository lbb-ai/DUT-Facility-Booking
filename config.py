import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY                     = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI        = os.environ.get('DATABASE_URL', 'sqlite:///campus_booking.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED               = True

    #  Mail 
    MAIL_SERVER         = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS',  'true').lower() == 'true'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_SUPPRESS_SEND  = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
    
    _display_name       = os.environ.get('MAIL_DISPLAY_NAME', 'DUT Campus Booking System')
    _sender_email       = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME', ''))
    MAIL_DEFAULT_SENDER = (_display_name, _sender_email)

    # reCAPTCHA 
    RECAPTCHA_SITE_KEY   = os.environ.get('RECAPTCHA_SITE_KEY',   '')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')

    # Microsoft OAuth 
    MICROSOFT_CLIENT_ID     = os.environ.get('MICROSOFT_CLIENT_ID',     '')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET', '')
    MICROSOFT_TENANT_ID     = os.environ.get('MICROSOFT_TENANT_ID',     'common')

    #  File uploads 
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))
    UPLOAD_FOLDER      = os.environ.get('UPLOAD_FOLDER', 'static/uploads/avatars')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    #  PayFast 
    PAYFAST_MERCHANT_ID  = os.environ.get('PAYFAST_MERCHANT_ID',  '10029317')
    PAYFAST_MERCHANT_KEY = os.environ.get('PAYFAST_MERCHANT_KEY', 'dgq8i39xb4b7p')
    PAYFAST_URL          = os.environ.get('PAYFAST_URL', 'https://sandbox.payfast.co.za/eng/process')

    # Security 
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG                 = False
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
