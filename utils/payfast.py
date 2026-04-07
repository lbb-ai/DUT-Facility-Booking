"""
PayFast helper — NO signature, minimal fields only.
Matches the pattern from the reference implementation.
"""
from flask import current_app


def build_payfast_form(order, user, return_url, cancel_url):
    """
    Returns {'action': url, 'fields': dict}
    No signature, no passphrase, no notify_url.
    Only the fields PayFast absolutely requires.
    """
    cfg = current_app.config

    fields = {
        'merchant_id':   cfg['PAYFAST_MERCHANT_ID'],
        'merchant_key':  cfg['PAYFAST_MERCHANT_KEY'],
        'return_url':    return_url,
        'cancel_url':    cancel_url,
        'amount':        f"{float(order.amount_total):.2f}",
        'item_name':     f"DUT Booking {order.reference}",
        'm_payment_id':  order.reference,
    }

    return {
        'action': cfg['PAYFAST_URL'],
        'fields': fields,
    }
