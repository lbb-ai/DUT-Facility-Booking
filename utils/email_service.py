"""
Email notification service.
All emails are suppressed in dev (MAIL_SUPPRESS_SEND=true).
Set MAIL_SUPPRESS_SEND=false and configure MAIL_* vars in .env to enable live sending.
For Gmail: enable 2FA and use an App Password as MAIL_PASSWORD.
"""
from flask import current_app
from flask_mail import Message
from extensions import mail
from dotenv import load_dotenv
import os


def _send(subject, recipients, html_body, pdf_bytes=None, pdf_filename='booking_confirmation.pdf'):
    """Core send with optional PDF attachment. Logs errors but never crashes the app."""
    try:
        msg = Message(
            subject    = subject,
            recipients = recipients,
            html       = html_body,
        )
        if pdf_bytes:
            msg.attach(
                filename    = pdf_filename,
                content_type= 'application/pdf',
                data        = pdf_bytes,
            )
        mail.send(msg)
        current_app.logger.info(f'[EMAIL OK] {subject} → {recipients}'
                                + (' (+PDF)' if pdf_bytes else ''))
    except Exception as e:
        current_app.logger.error(
            f'[EMAIL FAILED] {subject} → {recipients} | '
            f'Error: {e} | '
            f'Check MAIL_USERNAME / MAIL_PASSWORD in .env'
        )

def _generate_pdf_attachment(booking, base_url=os.environ.get('APP_URL')):
    """Generate PDF bytes for attachment. Returns None if generation fails."""
    try:
        from utils.pdf_generator import generate_confirmation_html
        html = generate_confirmation_html(booking, base_url=base_url)
        # Try weasyprint first
        try:
            from weasyprint import HTML as WP
            return WP(string=html).write_pdf()
        except ImportError:
            pass
        # Fallback: return HTML as a .html attachment (always works)
        return html.encode('utf-8')
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'PDF generation failed: {e}')
        return None


def _pdf_filename(booking):
    return f"DUT_Booking_{booking.id:05d}_{booking.booking_date.strftime('%Y%m%d')}.pdf"



# ── Shared HTML wrapper ───────────────────────────────────────
_WRAP = """
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  body  {{ font-family:Arial,sans-serif; background:#f4f6f9; margin:0; padding:0; }}
  .wrap {{ max-width:560px; margin:32px auto; background:#fff; border-radius:10px;
           overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,.08); }}
  .hdr  {{ background:#1a3a5c; padding:24px 28px; }}
  .hdr h1 {{ color:#fff; margin:0; font-size:1.1rem; font-weight:700; }}
  .hdr p  {{ color:rgba(255,255,255,.55); margin:4px 0 0; font-size:.8rem; }}
  .bdy  {{ padding:28px; }}
  .bdy h2 {{ color:#1a3a5c; font-size:1rem; margin-top:0; }}
  .bdy p  {{ color:#555; line-height:1.7; font-size:.88rem; }}
  .box  {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
           padding:14px 18px; margin:16px 0; }}
  .row  {{ display:flex; justify-content:space-between; padding:5px 0;
           border-bottom:1px solid #eee; font-size:.85rem; }}
  .row:last-child {{ border-bottom:none; }}
  .lbl  {{ color:#888; }}
  .val  {{ color:#1a3a5c; font-weight:600; }}
  .ftr  {{ background:#f8fafc; padding:16px 28px; text-align:center;
           border-top:1px solid #e2e8f0; }}
  .ftr p {{ color:#aaa; font-size:.72rem; margin:0; }}
  .badge-approved {{ background:#d1fae5; color:#065f46; padding:2px 10px;
                     border-radius:100px; font-size:.75rem; font-weight:700; }}
  .badge-rejected {{ background:#fde8e8; color:#9b1c1c; padding:2px 10px;
                     border-radius:100px; font-size:.75rem; font-weight:700; }}
  .badge-pending  {{ background:#fef3c7; color:#92400e; padding:2px 10px;
                     border-radius:100px; font-size:.75rem; font-weight:700; }}
</style></head><body>
<div class="wrap">
  <div class="hdr">
    <h1>DUT Campus Booking System</h1>
    <p>Dev Squad / Group 40 </p>
  </div>
  <div class="bdy">{BODY}</div>
  <div class="ftr"><p>Automated message — do not reply. © Dev Squad Group 40</p></div>
</div></body></html>
"""

def _wrap(body):
    return _WRAP.replace('{BODY}', body)


def _booking_rows(b, show_status=None):
    status_html = ''
    if show_status:
        css = {'approved': 'badge-approved', 'rejected': 'badge-rejected'}.get(show_status, 'badge-pending')
        status_html = f'<div class="row"><span class="lbl">Status</span><span class="val"><span class="{css}">{show_status.upper()}</span></span></div>'
    notes_html = f'<div class="row"><span class="lbl">Admin Notes</span><span class="val">{b.admin_notes}</span></div>' if b.admin_notes else ''
    return f"""
    <div class="box">
      <div class="row"><span class="lbl">Title</span><span class="val">{b.title}</span></div>
      <div class="row"><span class="lbl">Facility</span><span class="val">{b.facility.name}</span></div>
      <div class="row"><span class="lbl">Location</span><span class="val">{b.facility.location}</span></div>
      <div class="row"><span class="lbl">Date</span><span class="val">{b.booking_date.strftime('%A, %d %B %Y')}</span></div>
      <div class="row"><span class="lbl">Time</span><span class="val">{b.start_time.strftime('%H:%M')} – {b.end_time.strftime('%H:%M')}</span></div>
      <div class="row"><span class="lbl">Attendees</span><span class="val">{b.attendees}</span></div>
      {status_html}
      {notes_html}
    </div>"""


# ── Public functions ──────────────────────────────────────────

def send_booking_confirmation(booking):
    """User receives this when they submit a booking request."""
    body = f"""
    <h2>Booking Request Received</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Your booking request has been submitted and is awaiting admin approval.</p>
    {_booking_rows(booking, show_status='pending')}
    <p>You will be notified by email once an administrator reviews your request.</p>"""
    _send(
        subject=f'Booking Request Received – {booking.title}',
        recipients=[booking.user.email],
        html_body=_wrap(body)
    )


def send_booking_approved(booking):
    """User receives this when admin approves their booking. Attaches PDF confirmation with QR."""
    # Build QR section inline in email body
    qr_section = ''
    if booking.qr_token:
        try:
            from utils.qr_generator import generate_qr_base64
            qr_url = f"http://127.0.0.1:5000/checkin/{booking.qr_token}"
            qr_b64 = generate_qr_base64(qr_url, box_size=5)
            token_preview = booking.qr_token[:30] + '...'
            qr_section = f'''
    <div class="box" style="text-align:center">
      <div style="font-weight:700;color:#1a3a5c;margin-bottom:10px;font-size:.9rem">
        &#127903; Your Check-in QR Code
      </div>
      <img src="{qr_b64}" alt="Check-in QR"
           style="width:130px;height:130px;border:2px solid #1a3a5c;
                  border-radius:8px;padding:4px;background:#fff">
      <div style="margin-top:8px;font-size:.7rem;color:#94a3b8;font-family:monospace">
        {token_preview}
      </div>
      <div style="margin-top:6px;font-size:.75rem;color:#475569">
        Present this QR code or the attached PDF to the facility attendant on arrival.
      </div>
    </div>'''
        except Exception:
            pass

    body = f"""
    <h2>Booking Approved!</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Your booking has been <strong>approved</strong>. Please arrive on time.</p>
    {_booking_rows(booking, show_status='approved')}
    {qr_section}
    <p style="font-size:.8rem;color:#94a3b8">
      A PDF confirmation with your QR code is attached to this email.
      Print it or save it to your phone — the facility attendant will scan it on arrival.
    </p>"""

    pdf_bytes = _generate_pdf_attachment(booking)
    _send(
        subject      = f'\u2705 Booking Approved – {booking.title}',
        recipients   = [booking.user.email],
        html_body    = _wrap(body),
        pdf_bytes    = pdf_bytes,
        pdf_filename = _pdf_filename(booking),
    )


def send_booking_rejected(booking):
    """User receives this when admin rejects their booking."""
    body = f"""
    <h2> Booking Not Approved</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Unfortunately your booking request was <strong>not approved</strong>.</p>
    {_booking_rows(booking, show_status='rejected')}
    <p>You are welcome to submit a new request with an alternative date or facility.</p>"""
    _send(
        subject=f' Booking Rejected – {booking.title}',
        recipients=[booking.user.email],
        html_body=_wrap(body)
    )


def send_booking_cancelled(booking):
    """User receives this when a booking is cancelled."""
    body = f"""
    <h2>Booking Cancelled</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Your booking has been cancelled.</p>
    {_booking_rows(booking)}
    <p>Submit a new booking request if needed.</p>"""
    _send(
        subject=f'Booking Cancelled – {booking.title}',
        recipients=[booking.user.email],
        html_body=_wrap(body)
    )


def send_admin_new_request(booking, admin_email):
    """Admin receives this when a new booking is submitted."""
    body = f"""
    <h2>New Booking Request</h2>
    <p>A new booking request requires your review.</p>
    <div class="box">
      <div class="row"><span class="lbl">Submitted By</span>
        <span class="val">{booking.user.full_name} ({booking.user.student_number})</span></div>
      <div class="row"><span class="lbl">Title</span><span class="val">{booking.title}</span></div>
      <div class="row"><span class="lbl">Facility</span><span class="val">{booking.facility.name}</span></div>
      <div class="row"><span class="lbl">Date</span>
        <span class="val">{booking.booking_date.strftime('%A, %d %B %Y')}</span></div>
      <div class="row"><span class="lbl">Time</span>
        <span class="val">{booking.start_time.strftime('%H:%M')} – {booking.end_time.strftime('%H:%M')}</span></div>
    </div>
    <p>Log in to the admin panel to approve or reject this request.</p>"""
    _send(
        subject=f'[Action Required] New Booking: {booking.title}',
        recipients=[admin_email],
        html_body=_wrap(body)
    )


def send_password_reset(user, reset_url):
    """Send password reset link to the user."""
    body = f"""
    <h2> Password Reset Request</h2>
    <p>Hi <strong>{user.name}</strong>,<br>
    We received a request to reset the password for your account.
    Click the button below to set a new password. This link expires in <strong>1 hour</strong>.</p>
    <div style="text-align:center;margin:28px 0">
      <a href="{reset_url}"
         style="background:#1a3a5c;color:#fff;text-decoration:none;padding:12px 28px;
                border-radius:8px;font-weight:700;font-size:.9rem;display:inline-block">
        Reset My Password
      </a>
    </div>
    <div class="box" style="font-size:.8rem;color:#888">
      <strong>Didn't request this?</strong> You can safely ignore this email —
      your password will not change unless you click the link above.
    </div>
    <p style="font-size:.78rem;color:#aaa;margin-top:12px">
      Or copy this link: <span style="font-family:monospace;color:#1a3a5c">{reset_url}</span>
    </p>"""
    _send(
        subject='Reset Your Campus Booking Password',
        recipients=[user.email],
        html_body=_wrap(body)
    )


def send_welcome_oauth(user):
    """Welcome email for OAuth sign-ups."""
    body = f"""
    <h2> Welcome to Campus Facility Booking!  </h2>
    <p>Hi <strong>{user.name}</strong>,<br>
    Your account has been created using your <strong>Microsoft account</strong>.
    You can sign in anytime using the <em>Sign in with Microsoft</em> button.</p>
    <div class="box">
      <div class="row"><span class="lbl">Name</span>
        <span class="val">{user.full_name}</span></div>
      <div class="row"><span class="lbl">Student Number</span>
        <span class="val">{user.student_number}</span></div>
      <div class="row"><span class="lbl">Email</span>
        <span class="val">{user.email}</span></div>
      <div class="row"><span class="lbl">Role</span>
        <span class="val">{user.role.title()}</span></div>
    </div>
    <p>Start by browsing available facilities and submitting your first booking request.</p>"""
    _send(
        subject='Welcome to Campus Facility Booking System',
        recipients=[user.email],
        html_body=_wrap(body)
    )


def send_booking_reminder(booking):
    """30-minute reminder email with QR in body + PDF confirmation attached."""
    qr_section = ''
    if booking.qr_token:
        try:
            from utils.qr_generator import generate_qr_base64
            qr_url = f"http://127.0.0.1:5000/checkin/{booking.qr_token}"
            qr_b64 = generate_qr_base64(qr_url, box_size=5)
            token_preview = booking.qr_token[:30] + '...'
            qr_section = f'''
    <div class="box" style="text-align:center">
      <div style="font-weight:700;color:#1a3a5c;margin-bottom:10px;font-size:.9rem">
        &#127903; Your Check-in QR Code
      </div>
      <img src="{qr_b64}" alt="Check-in QR Code"
           style="width:130px;height:130px;border:2px solid #1a3a5c;
                  border-radius:8px;padding:4px;background:#fff">
      <div style="margin-top:8px;font-size:.7rem;color:#94a3b8;font-family:monospace">
        {token_preview}
      </div>
      <div style="margin-top:6px;font-size:.75rem;color:#475569">
        Show this QR code or the attached PDF to the facility attendant on arrival.
      </div>
    </div>'''
        except Exception:
            pass

    campus_str = (' &middot; ' + booking.facility.campus) if booking.facility.campus else ''

    body = f"""
    <h2> Booking Reminder &mdash; Starting in 30 Minutes</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    This is a reminder that your booking starts soon. Please make your way to the facility now.</p>
    <div class="box">
      <div class="row"><span class="lbl">Booking</span>
        <span class="val">{booking.title}</span></div>
      <div class="row"><span class="lbl">Facility</span>
        <span class="val">{booking.facility.name}</span></div>
      <div class="row"><span class="lbl">Location</span>
        <span class="val">{booking.facility.location}{campus_str}</span></div>
      <div class="row"><span class="lbl">Date</span>
        <span class="val">{booking.booking_date.strftime('%A, %d %B %Y')}</span></div>
      <div class="row"><span class="lbl">Time</span>
        <span class="val">{booking.start_time.strftime('%H:%M')} &ndash; {booking.end_time.strftime('%H:%M')}</span></div>
      <div class="row"><span class="lbl">Attendees</span>
        <span class="val">{booking.attendees}</span></div>
    </div>
    {qr_section}
    <p style="font-size:.8rem;color:#94a3b8">
      If you can no longer attend, please cancel via the booking system before the session starts.
    </p>"""

    pdf_bytes = _generate_pdf_attachment(booking)
    _send(
        subject      = f'\u23f0 Reminder: "{booking.title}" starts in 30 minutes',
        recipients   = [booking.user.email],
        html_body    = _wrap(body),
        pdf_bytes    = pdf_bytes,
        pdf_filename = _pdf_filename(booking),
    )


def send_external_booking_confirmed(booking):
    """External user receives this after PayFast payment — with PDF + QR attached."""
    qr_section = ''
    if booking.qr_token:
        try:
            from utils.qr_generator import generate_qr_base64
            qr_url = f"http://127.0.0.1:5000/checkin/{booking.qr_token}"
            qr_b64 = generate_qr_base64(qr_url, box_size=5)
            token_preview = booking.qr_token[:30] + '...'
            qr_section = f'''
    <div class="box" style="text-align:center">
      <div style="font-weight:700;color:#5b21b6;margin-bottom:10px;font-size:.9rem">
        &#127903; Your Check-in QR Code
      </div>
      <img src="{qr_b64}" alt="Check-in QR"
           style="width:130px;height:130px;border:2px solid #5b21b6;
                  border-radius:8px;padding:4px;background:#fff">
      <div style="margin-top:8px;font-size:.7rem;color:#94a3b8;font-family:monospace">
        {token_preview}
      </div>
      <div style="margin-top:6px;font-size:.75rem;color:#475569">
        Present this QR code or the attached PDF to the facility attendant on arrival.
      </div>
    </div>'''
        except Exception:
            pass

    amount_str = f"R{float(booking.amount_paid):.2f}" if booking.amount_paid else ''
    campus_str = (' &middot; ' + booking.facility.campus) if booking.facility.campus else ''

    body = f"""
    <h2> Booking Confirmed &amp; Payment Received!</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Thank you for your payment. Your facility booking has been confirmed.</p>
    <div class="box">
      <div class="row"><span class="lbl">Booking</span>
        <span class="val">{booking.title}</span></div>
      <div class="row"><span class="lbl">Facility</span>
        <span class="val">{booking.facility.name}</span></div>
      <div class="row"><span class="lbl">Location</span>
        <span class="val">{booking.facility.location}{campus_str}</span></div>
      <div class="row"><span class="lbl">Date</span>
        <span class="val">{booking.booking_date.strftime('%A, %d %B %Y')}</span></div>
      <div class="row"><span class="lbl">Time</span>
        <span class="val">{booking.start_time.strftime('%H:%M')} &ndash; {booking.end_time.strftime('%H:%M')}</span></div>
      <div class="row"><span class="lbl">Attendees</span>
        <span class="val">{booking.attendees}</span></div>
      {f'<div class="row"><span class="lbl">Amount Paid</span><span class="val" style="color:#5b21b6;font-weight:700">{amount_str}</span></div>' if amount_str else ''}
      <div class="row"><span class="lbl">Status</span>
        <span class="val" style="color:#5b21b6;font-weight:700">&#10003; PAID</span></div>
    </div>
    {qr_section}
    <p style="font-size:.8rem;color:#94a3b8">
      A PDF confirmation with your QR code is attached. Print it or save it — the facility
      attendant will scan it when you arrive. A 30-minute reminder will also be sent before your session.
    </p>"""

    pdf_bytes = _generate_pdf_attachment(booking)
    _send(
        subject      = f'\U0001f4b3 Booking Confirmed & Paid – {booking.title}',
        recipients   = [booking.user.email],
        html_body    = _wrap(body),
        pdf_bytes    = pdf_bytes,
        pdf_filename = _pdf_filename(booking),
    )


def send_booking_rescheduled(booking, old_date, old_start, old_end):
    """Notify user their booking has been rescheduled to a new date/time."""
    body = f"""
    <h2> &#128197; Booking Rescheduled &#x1F4C5; </h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Your booking has been successfully rescheduled. Here are the updated details:</p>

    <div class="box">
      <div style="margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #eee">
        <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;
                    color:#94a3b8;font-weight:700;margin-bottom:4px">Previous Schedule</div>
        <div style="color:#94a3b8;text-decoration:line-through;font-size:.88rem">
          {old_date.strftime('%A, %d %B %Y')} &mdash;
          {old_start.strftime('%H:%M')} &ndash; {old_end.strftime('%H:%M')}
        </div>
      </div>
      <div>
        <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;
                    color:#065f46;font-weight:700;margin-bottom:4px">New Schedule</div>
        <div style="color:#1a3a5c;font-weight:700;font-size:.95rem">
          {booking.booking_date.strftime('%A, %d %B %Y')} &mdash;
          {booking.start_time.strftime('%H:%M')} &ndash; {booking.end_time.strftime('%H:%M')}
        </div>
      </div>
    </div>

    {_booking_rows(booking, show_status=booking.status)}
    <p style="font-size:.8rem;color:#94a3b8">
      Your QR code remains valid for the new date. A PDF confirmation is attached.
    </p>"""

    pdf_bytes = _generate_pdf_attachment(booking)
    _send(
        subject      = f'&#128197; Booking Rescheduled – {booking.title}',
        recipients   = [booking.user.email],
        html_body    = _wrap(body),
        pdf_bytes    = pdf_bytes,
        pdf_filename = _pdf_filename(booking),
    )


def send_checkin_confirmed(booking, scanned_by):
    """Notify user their attendance has been confirmed by staff."""
    body = f"""
    <h2> Attendance Confirmed!</h2>
    <p>Hi <strong>{booking.user.name}</strong>,<br>
    Your attendance for the following booking has been confirmed.</p>
    <div class="box">
      <div class="row"><span class="lbl">Booking</span>
        <span class="val">{booking.title}</span></div>
      <div class="row"><span class="lbl">Facility</span>
        <span class="val">{booking.facility.name}</span></div>
      <div class="row"><span class="lbl">Date</span>
        <span class="val">{booking.booking_date.strftime('%A, %d %B %Y')}</span></div>
      <div class="row"><span class="lbl">Checked In At</span>
        <span class="val">{booking.attended_at.strftime('%H:%M on %d %b %Y')}</span></div>
      <div class="row"><span class="lbl">Verified By</span>
        <span class="val">{scanned_by.full_name}</span></div>
    </div>
    <p style="font-size:.8rem;color:#94a3b8">Thank you for using the Campus Facility Booking System.</p>"""

    _send(
        subject=f' Attendance Confirmed — {booking.title}',
        recipients=[booking.user.email],
        html_body=_wrap(body)
    )
