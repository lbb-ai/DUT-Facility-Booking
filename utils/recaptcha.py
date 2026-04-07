"""
Google reCAPTCHA v2 verification helper.
Verifies the g-recaptcha-response token with Google's siteverify API.
"""
import requests
from flask import current_app


def verify_recaptcha(token):
    """
    Returns True if the reCAPTCHA token is valid.
    Returns True automatically in dev when RECAPTCHA_SECRET_KEY is not set
    (so the form still works without keys configured).
    """
    secret = current_app.config.get('RECAPTCHA_SECRET_KEY', '')
    if not secret or secret == 'your-recaptcha-secret-key':
        current_app.logger.warning('reCAPTCHA secret key not configured — skipping verification.')
        return True

    if not token:
        return False

    try:
        resp = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': secret, 'response': token},
            timeout=5
        )
        result = resp.json()
        return result.get('success', False)
    except Exception as e:
        current_app.logger.warning(f'reCAPTCHA verification failed: {e}')
        return False
