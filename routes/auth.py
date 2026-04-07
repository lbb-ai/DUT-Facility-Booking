from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User
from utils.recaptcha import verify_recaptcha
from utils.email_service import send_password_reset, send_welcome_oauth
import msal, requests as http_requests, os

auth = Blueprint('auth', __name__, url_prefix='/auth')



#  Register
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    recaptcha_site_key = current_app.config.get('RECAPTCHA_SITE_KEY', '')

    if request.method == 'POST':
       
        recaptcha_token = request.form.get('g-recaptcha-response', '')
        if not verify_recaptcha(recaptcha_token):
            flash('reCAPTCHA verification failed. Please tick the checkbox and try again.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        student_number = request.form.get('student_number', '').strip() or None
        name           = request.form.get('name', '').strip()
        surname        = request.form.get('surname', '').strip()
        email          = request.form.get('email', '').strip().lower()
        password       = request.form.get('password', '')
        confirm        = request.form.get('confirm_password', '')
        role           = request.form.get('role', 'student')
        organisation   = request.form.get('organisation', '').strip() or None
        phone          = request.form.get('phone', '').strip() or None

        if role not in ['student', 'staff', 'external']:
            role = 'student'

        # student/staff must have a number; external must not
        if role in ['student', 'staff'] and not student_number:
            flash('Student/staff number is required.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        if not all([name, surname, email, password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        if student_number and User.query.filter_by(student_number=student_number).first():
            flash('Student/staff number already registered.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)

        user = User(student_number=student_number, name=name, surname=surname,
                    email=email, role=role, organisation=organisation, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', recaptcha_site_key=recaptcha_site_key)



#  Login
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    ms_configured = bool(current_app.config.get('MICROSOFT_CLIENT_ID') and
                         current_app.config.get('MICROSOFT_CLIENT_ID') != 'your-azure-app-client-id')

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')
        remember   = request.form.get('remember') == 'on'

        user = User.query.filter(
            (User.student_number == identifier) |
            (User.email == identifier.lower())
        ).first()

        if user and user.is_oauth_user() and not user.password_hash:
            flash('This account uses Microsoft sign-in. Please use the button below.', 'warning')
            return render_template('auth/login.html', ms_configured=ms_configured)

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        flash('Invalid credentials. Please try again.', 'danger')

    return render_template('auth/login.html', ms_configured=ms_configured)



#  Logout
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))



#  Forgot Password
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()

        flash('If an account with that email exists, a reset link has been sent.', 'info')

        if user and not user.is_oauth_user():
            token     = user.generate_reset_token()
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                send_password_reset(user, reset_url)
            except Exception as e:
                current_app.logger.warning(f'Failed to send reset email: {e}')

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


#  Reset Password
@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash('This reset link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        flash('Password reset successfully! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


#  Profile — view & edit
@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            name    = request.form.get('name', '').strip()
            surname = request.form.get('surname', '').strip()
            bio     = request.form.get('bio', '').strip()[:500]
            phone   = request.form.get('phone', '').strip()[:30]

            if not name or not surname:
                flash('Name and surname are required.', 'danger')
                return redirect(url_for('auth.profile'))

            current_user.name    = name
            current_user.surname = surname
            current_user.bio     = bio or None
            current_user.phone   = phone or None

            # Profile picture upload
            file = request.files.get('profile_picture')
            if file and file.filename:
                from utils.file_upload import save_avatar
                try:
                    filename = save_avatar(file, old_filename=current_user.profile_picture)
                    current_user.profile_picture = filename
                except ValueError as e:
                    flash(str(e), 'danger')
                    return redirect(url_for('auth.profile'))

            db.session.commit()
            flash('Profile updated successfully.', 'success')

        elif action == 'remove_avatar':
            if current_user.profile_picture:
                from utils.file_upload import delete_avatar
                delete_avatar(current_user.profile_picture)
                current_user.profile_picture = None
                db.session.commit()
                flash('Profile picture removed.', 'info')

        elif action == 'change_password':
            if current_user.is_oauth_user() and not current_user.password_hash:
                flash('Password cannot be changed for Microsoft sign-in accounts.', 'warning')
                return redirect(url_for('auth.profile'))

            current_pw = request.form.get('current_password', '')
            new_pw     = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('auth.profile'))

            if len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
                return redirect(url_for('auth.profile'))

            if new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('auth.profile'))

            current_user.set_password(new_pw)
            db.session.commit()
            flash('Password changed successfully.', 'success')

        return redirect(url_for('auth.profile'))

    # GET — load booking stats for the profile card
    from models import Booking
    stats = {
        'total':    Booking.query.filter_by(user_id=current_user.id).count(),
        'approved': Booking.query.filter_by(user_id=current_user.id, status='approved').count(),
        'pending':  Booking.query.filter_by(user_id=current_user.id, status='pending').count(),
    }
    return render_template('auth/profile.html', stats=stats)



#  MicroSoft OAuth
def _msal_app():
    return msal.ConfidentialClientApplication(
        client_id     = current_app.config['MICROSOFT_CLIENT_ID'],
        client_credential = current_app.config['MICROSOFT_CLIENT_SECRET'],
        authority     = f"https://login.microsoftonline.com/{current_app.config['MICROSOFT_TENANT_ID']}",
    )

def _ms_callback_url():
    return url_for('auth.microsoft_callback', _external=True)


@auth.route('/microsoft')
def microsoft_login():
    client_id = current_app.config.get('MICROSOFT_CLIENT_ID', '')
    if not client_id or client_id == 'your-azure-app-client-id':
        flash('Microsoft sign-in is not configured yet. Contact the administrator.', 'warning')
        return redirect(url_for('auth.login'))

    flow = _msal_app().initiate_auth_code_flow(
        scopes        = ['User.Read', 'email', 'profile', 'openid'],
        redirect_uri  = _ms_callback_url(),
    )
    session['msal_flow'] = flow
    return redirect(flow['auth_uri'])


@auth.route('/microsoft/callback')
def microsoft_callback():
    flow = session.pop('msal_flow', None)
    if not flow:
        flash('Microsoft sign-in session expired. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        result = _msal_app().acquire_token_by_auth_code_flow(flow, request.args)
    except Exception as e:
        current_app.logger.error(f'MSAL error: {e}')
        flash('Microsoft sign-in failed. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    if 'error' in result:
        flash(f"Microsoft sign-in error: {result.get('error_description', 'Unknown error')}", 'danger')
        return redirect(url_for('auth.login'))

    # Fetch user profile from Graph API
    graph_token = result.get('access_token')
    graph_resp  = http_requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': f'Bearer {graph_token}'},
        timeout=10
    )
    ms_user = graph_resp.json()

    ms_id    = ms_user.get('id')
    ms_email = (ms_user.get('mail') or ms_user.get('userPrincipalName', '')).lower()
    ms_name  = ms_user.get('givenName') or ms_user.get('displayName', 'User')
    ms_sname = ms_user.get('surname') or ''

    if not ms_id or not ms_email:
        flash('Could not retrieve your Microsoft account details. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    # Find or create user
    user = User.query.filter_by(oauth_id=ms_id).first()

    if not user:
        # Check if email already registered with normal account
        existing = User.query.filter_by(email=ms_email).first()
        if existing:
            # Link the OAuth ID to the existing account
            existing.oauth_provider = 'microsoft'
            existing.oauth_id       = ms_id
            db.session.commit()
            user = existing
        else:
            # Create new OAuth user — derive student number from email prefix
            email_prefix   = ms_email.split('@')[0]
            student_number = email_prefix[:20]
            # Ensure uniqueness
            if User.query.filter_by(student_number=student_number).first():
                student_number = student_number[:16] + ms_id[-4:]

            user = User(
                student_number  = student_number,
                name            = ms_name or 'Microsoft',
                surname         = ms_sname or 'User',
                email           = ms_email,
                oauth_provider  = 'microsoft',
                oauth_id        = ms_id,
                role            = 'student',
            )
            # Set a random unusable password so the field is not null
            import secrets as _sec
            user.set_password(_sec.token_urlsafe(32))
            user.password_hash = None  # mark as OAuth-only
            db.session.add(user)
            db.session.commit()
            try:
                send_welcome_oauth(user)
            except Exception:
                pass

    if not user.is_active:
        flash('Your account is inactive. Please contact an administrator.', 'danger')
        return redirect(url_for('auth.login'))

    login_user(user, remember=True)
    flash(f'Signed in with Microsoft as {user.full_name}!', 'success')
    return redirect(url_for('main.dashboard'))
