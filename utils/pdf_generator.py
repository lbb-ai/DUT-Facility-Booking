"""
PDF Booking Confirmation Generator.
Returns a self-contained HTML page styled for A4 print.
Access via /bookings/<id>/confirmation — user clicks File → Print → Save as PDF.
"""
from datetime import datetime


def generate_confirmation_html(booking, base_url='http://127.0.0.1:5000'):
    """Return a complete, printable HTML confirmation page with embedded QR code."""
    generated_at = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')

    # QR code section 
    qr_html = ''
    if booking.qr_token:
        try:
            from utils.qr_generator import generate_qr_base64
            qr_url  = f"{base_url}/checkin/{booking.qr_token}"
            qr_b64  = generate_qr_base64(qr_url, box_size=8)
            token_preview = booking.qr_token[:32] + '...'
            qr_html = (
                '<div style="padding:20px 44px 0;page-break-inside:avoid">'
                '<div style="display:flex;align-items:center;gap:24px;background:#f8fafc;'
                'border:1px solid #e2e8f0;border-radius:12px;padding:18px 22px">'
                '<div style="flex-shrink:0">'
                '<img src="' + qr_b64 + '" alt="Check-in QR" '
                'style="width:130px;height:130px;border:2px solid #1a3a5c;'
                'border-radius:8px;padding:4px;background:#fff">'
                '</div>'
                '<div>'
                '<div style="font-weight:700;color:#1a3a5c;font-size:.95rem;margin-bottom:6px">'
                '&#127903; Check-in QR Code</div>'
                '<div style="font-size:.78rem;color:#475569;line-height:1.7">'
                'Present this document to the facility attendant on arrival.<br>'
                'They will scan this QR code to confirm your attendance.<br>'
                '<span style="font-family:monospace;font-size:.68rem;color:#94a3b8">'
                'Token: ' + token_preview + '</span>'
                '</div>'
                '</div>'
                '</div>'
                '</div>'
            )
        except Exception:
            pass

    # Optional rows 
    row_style = 'color:#888;font-size:.85rem;padding:8px 0;border-bottom:1px solid #f1f5f9;width:160px'
    val_style = 'color:#1a3a5c;font-weight:600;font-size:.85rem;padding:8px 0;border-bottom:1px solid #f1f5f9'

    recurring_row = ''
    if booking.is_recurring and booking.recurrence_pattern:
        end = f' until {booking.recurrence_end_date.strftime("%d %b %Y")}' if booking.recurrence_end_date else ''
        recurring_row = f'<tr><td style="{row_style}">Recurrence</td><td style="{val_style}">{booking.recurrence_pattern.title()}{end}</td></tr>'

    notes_row = ''
    if booking.admin_notes:
        notes_row = f'<tr><td style="{row_style}">Admin Notes</td><td style="{val_style}">{booking.admin_notes}</td></tr>'

    amount_row = ''
    if booking.amount_paid:
        amount_row = f'<tr><td style="{row_style}">Amount Paid</td><td style="color:#5b21b6;font-weight:700;font-size:.85rem;padding:8px 0;border-bottom:1px solid #f1f5f9;font-family:JetBrains Mono,monospace">R{float(booking.amount_paid):.2f}</td></tr>'

    attended_row = ''
    if booking.is_attended:
        attended_row = f'<tr><td style="{row_style}">Attended</td><td style="color:#065f46;font-weight:700;font-size:.85rem;padding:8px 0;border-bottom:1px solid #f1f5f9">&#10003; {booking.attended_at.strftime("%d %b %Y at %H:%M")}</td></tr>'

    equipment_html = ''
    if booking.facility.equipment_list:
        tags = ''.join(
            f'<span style="display:inline-block;background:#f0f4ff;color:#1a3a5c;'
            f'font-size:.72rem;padding:3px 10px;border-radius:6px;margin:3px 2px 3px 0">'
            f'&#10003; {eq}</span>'
            for eq in booking.facility.equipment_list
        )
        equipment_html = (
            '<div style="margin:20px 44px 0">'
            '<div style="font-size:.6rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:.12em;color:#94a3b8;margin-bottom:8px;font-family:monospace">'
            'Equipment &amp; Resources</div>' + tags + '</div>'
        )

    status_colour = {'approved': '#34d399', 'rejected': '#f87171',
                     'pending': '#fbbf24', 'paid': '#a78bfa'}.get(booking.status, '#94a3b8')
    status_label = ('PAID' if booking.status == 'paid' else booking.status.upper())
    campus_str = (' &middot; ' + booking.facility.campus) if booking.facility.campus else ''
    id_str = booking.user.student_number or booking.user.email
    org_str = (' &mdash; ' + booking.user.organisation) if booking.user.organisation else ''

    html = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        f'<title>Booking Confirmation #{booking.id:05d}</title>'
        '<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700'
        '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
        '<style>'
        '* { box-sizing:border-box; margin:0; padding:0; }'
        "body { font-family:'Sora',Arial,sans-serif; background:#f0f4f8;"
        '  display:flex; flex-direction:column; align-items:center; padding:40px 20px; }'
        '.page { background:#fff; width:794px; min-height:980px;'
        '  box-shadow:0 8px 40px rgba(0,0,0,.12); border-radius:4px; overflow:hidden; }'
        '@media print { body { background:#fff; padding:0; }'
        '  .page { box-shadow:none; width:100%; } .no-print { display:none!important; } }'
        '</style></head><body>'
        '<div class="page">'

        # Header
        '<div style="background:linear-gradient(135deg,#1a3a5c,#2563a8);padding:36px 44px;'
        'position:relative;overflow:hidden">'
        '<div style="position:absolute;right:-50px;top:-50px;width:180px;height:180px;'
        'border-radius:50%;background:rgba(255,255,255,.06)"></div>'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        '<div>'
        '<div style="color:#fff;font-weight:700;font-size:1.25rem;margin-bottom:4px">'
        '&#127979; Campus Facility Booking System</div>'
        '<div style="color:rgba(255,255,255,.5);font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'text-transform:uppercase;letter-spacing:.08em">Dev Squad / Group 40  </div>'
        '</div>'
        '<div style="text-align:right">'
        '<div style="color:rgba(255,255,255,.45);font-size:.65rem;font-family:JetBrains Mono,monospace;'
        'text-transform:uppercase">Ref No.</div>'
        f'<div style="color:#e8a020;font-size:1.7rem;font-weight:700;font-family:JetBrains Mono,monospace;line-height:1">#{booking.id:05d}</div>'
        '</div></div>'
        f'<div style="margin-top:20px;display:inline-flex;align-items:center;gap:8px;'
        f'background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);'
        f'border-radius:100px;padding:5px 14px">'
        f'<div style="width:8px;height:8px;border-radius:50%;background:{status_colour}"></div>'
        f'<span style="color:#fff;font-size:.8rem;font-weight:600">{status_label}</span>'
        '</div></div>'

        # Key info grid
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:28px 44px 0">'
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px">'
        '<div style="font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;font-weight:700;margin-bottom:6px">Date</div>'
        f'<div style="font-weight:700;color:#1a3a5c;font-size:1.05rem">{booking.booking_date.strftime("%d %B %Y")}</div>'
        f'<div style="color:#64748b;font-size:.8rem">{booking.booking_date.strftime("%A")}</div></div>'
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px">'
        '<div style="font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;font-weight:700;margin-bottom:6px">Time Slot</div>'
        f'<div style="font-weight:700;color:#1a3a5c;font-size:1.05rem;font-family:JetBrains Mono,monospace">{booking.start_time.strftime("%H:%M")} &ndash; {booking.end_time.strftime("%H:%M")}</div>'
        f'<div style="color:#64748b;font-size:.8rem">{booking.duration_hours:.1f} hours</div></div>'
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px">'
        '<div style="font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;font-weight:700;margin-bottom:6px">Facility</div>'
        f'<div style="font-weight:700;color:#1a3a5c;font-size:1rem">{booking.facility.name}</div>'
        f'<div style="color:#64748b;font-size:.8rem">{booking.facility.location}{campus_str}</div></div>'
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px">'
        '<div style="font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;font-weight:700;margin-bottom:6px">Attendees</div>'
        f'<div style="font-weight:700;color:#1a3a5c;font-size:1.05rem">{booking.attendees}</div>'
        f'<div style="color:#64748b;font-size:.8rem">Capacity: {booking.facility.capacity}</div></div>'
        '</div>'

        # Details table
        '<div style="padding:24px 44px 0">'
        '<div style="font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;'
        'color:#94a3b8;margin-bottom:10px;font-family:monospace">Booking Details</div>'
        '<table style="width:100%;border-collapse:collapse">'
        f'<tr><td style="{row_style}">Booking Title</td><td style="{val_style}">{booking.title}</td></tr>'
        f'<tr><td style="{row_style}">Booked By</td><td style="{val_style}">{booking.user.full_name}</td></tr>'
        f'<tr><td style="{row_style}">ID / Number</td><td style="{val_style};font-family:JetBrains Mono,monospace">{id_str}</td></tr>'
        f'<tr><td style="{row_style}">Role</td><td style="{val_style}">{booking.user.role.title()}{org_str}</td></tr>'
        f'{recurring_row}{notes_row}{amount_row}{attended_row}'
        f'<tr><td style="color:#888;font-size:.85rem;padding:8px 0">Submitted</td>'
        f'<td style="color:#1a3a5c;font-weight:600;font-size:.85rem;padding:8px 0">{booking.created_at.strftime("%d %b %Y at %H:%M")}</td></tr>'
        '</table></div>'

        # Reason
        '<div style="padding:20px 44px 0">'
        '<div style="font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;'
        'color:#94a3b8;margin-bottom:8px;font-family:monospace">Reason for Booking</div>'
        f'<div style="background:#f8fafc;border-left:4px solid #e8a020;border-radius:0 8px 8px 0;'
        f'padding:14px 18px;color:#475569;font-size:.875rem;line-height:1.7">{booking.reason}</div></div>'

        # Equipment
        f'{equipment_html}'

        # QR code
        f'{qr_html}'

        # Footer
        '<div style="background:#f8fafc;border-top:2px solid #e2e8f0;padding:20px 44px;'
        'display:flex;justify-content:space-between;align-items:center;margin-top:20px">'
        '<div>'
        '<div style="font-size:.8rem;font-weight:700;color:#1a3a5c">Campus Facility Booking System</div>'
        '<div style="font-size:.7rem;color:#94a3b8">Dev Squad / Group 40 </div>'
        '<div style="font-size:.7rem;color:#94a3b8">Official booking confirmation document</div>'
        '</div>'
        '<div style="text-align:right">'
        f'<div style="font-size:.65rem;color:#cbd5e1;font-family:JetBrains Mono,monospace">Generated: {generated_at}</div>'
        f'<div style="font-size:.65rem;color:#cbd5e1;font-family:JetBrains Mono,monospace">CBS-{booking.id:05d}</div>'
        '</div></div>'
        '</div>'

        # Print button
        '<div class="no-print" style="margin-top:20px;text-align:center">'
        '<button onclick="window.print()" style="background:#e8a020;color:#1a3a5c;border:none;'
        'padding:11px 30px;border-radius:8px;font-weight:700;font-size:.9rem;cursor:pointer;'
        "font-family:'Sora',sans-serif\">&#128424; Print / Save as PDF</button>"
        '<a href="javascript:history.back()" style="color:#94a3b8;text-decoration:none;'
        'font-size:.8rem;margin-left:16px">&#8592; Back to booking</a>'
        '</div>'
        '</body></html>'
    )
    return html


def try_generate_pdf_bytes(booking):
    """Try server-side PDF via weasyprint. Returns None if not installed."""
    try:
        from weasyprint import HTML as WP
        return WP(string=generate_confirmation_html(booking)).write_pdf()
    except ImportError:
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'weasyprint error: {e}')
        return None
