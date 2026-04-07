"""
Profile picture upload and processing utility.
Resizes images to 256x256 and saves as WebP for consistency.
"""
import os
import uuid
from flask import current_app
from PIL import Image


ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def save_avatar(file_storage, old_filename=None):
    """
    Process and save an uploaded avatar.
    Returns the new filename (stored in static/uploads/avatars/).
    Deletes the old file if provided.
    """
    if not file_storage or file_storage.filename == '':
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError('File type not allowed. Use PNG, JPG, GIF or WebP.')

    upload_dir = os.path.join(current_app.root_path,
                              current_app.config.get('UPLOAD_FOLDER', 'static/uploads/avatars'))
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.webp"
    save_path = os.path.join(upload_dir, filename)

    img = Image.open(file_storage.stream)
    img = img.convert('RGB')

    # Square crop from center
    w, h  = img.size
    side  = min(w, h)
    left  = (w - side) // 2
    top   = (h - side) // 2
    img   = img.crop((left, top, left + side, top + side))
    img   = img.resize((256, 256), Image.LANCZOS)
    img.save(save_path, 'WEBP', quality=85)

    # Delete old avatar
    if old_filename:
        old_path = os.path.join(upload_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    return filename


def delete_avatar(filename):
    if not filename:
        return
    upload_dir = os.path.join(current_app.root_path,
                              current_app.config.get('UPLOAD_FOLDER', 'static/uploads/avatars'))
    path = os.path.join(upload_dir, filename)
    if os.path.exists(path):
        os.remove(path)


def save_facility_image(file_storage, old_filename=None):
    """
    Process and save a facility image.
    Resizes to 800x520 (landscape) and saves as WebP.
    Returns the new filename.
    """
    if not file_storage or file_storage.filename == '':
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError('File type not allowed. Use PNG, JPG, GIF or WebP.')

    import os
    from flask import current_app
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'facilities')
    os.makedirs(upload_dir, exist_ok=True)

    filename  = f"{uuid.uuid4().hex}.webp"
    save_path = os.path.join(upload_dir, filename)

    img = Image.open(file_storage.stream).convert('RGB')

    # Smart crop to 800×520 (landscape)
    target_w, target_h = 800, 520
    w, h = img.size
    ratio = max(target_w / w, target_h / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    img  = img.crop((left, top, left + target_w, top + target_h))
    img.save(save_path, 'WEBP', quality=85)

    if old_filename:
        old_path = os.path.join(upload_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    return filename


def delete_facility_image(filename):
    if not filename:
        return
    import os
    from flask import current_app
    path = os.path.join(current_app.root_path, 'static', 'uploads', 'facilities', filename)
    if os.path.exists(path):
        os.remove(path)
