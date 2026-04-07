"""
QR code generation utility.
Generates a PNG QR code encoding the check-in URL for a booking.
"""
import io
import base64
import qrcode
from qrcode.image.pil import PilImage


def generate_qr_png(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """Generate QR code PNG and return as bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#1a3a5c', back_color='white', image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def generate_qr_base64(data: str, box_size: int = 8, border: int = 2) -> str:
    """Return QR code as base64 data URI — embeds directly in HTML/email."""
    png_bytes = generate_qr_png(data, box_size, border)
    b64 = base64.b64encode(png_bytes).decode('utf-8')
    return f"data:image/png;base64,{b64}"
