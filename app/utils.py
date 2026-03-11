import os
import uuid
from datetime import datetime
from functools import wraps
from flask import abort, current_app
from flask_login import current_user


def calc_twi(raw_int, raw_ci, raw_co, raw_ext, init_int, init_ci, init_co, init_ext):
    """Calculate TWI values from raw form strings, allowing partial fills.
    Returns a dict with all fields, or None if no data at all."""
    twi_int = float(raw_int) if raw_int else None
    twi_ci  = float(raw_ci)  if raw_ci  else None
    twi_co  = float(raw_co)  if raw_co  else None
    twi_ext = float(raw_ext) if raw_ext else None

    filled = [v for v in [twi_int, twi_ci, twi_co, twi_ext] if v is not None]
    if not filled:
        return None

    twi_avg = round(sum(filled) / len(filled), 2)

    pct_int = round((twi_int / init_int) * 100, 1) if twi_int is not None and init_int else None
    pct_ci  = round((twi_ci  / init_ci)  * 100, 1) if twi_ci  is not None and init_ci  else None
    pct_co  = round((twi_co  / init_co)  * 100, 1) if twi_co  is not None and init_co  else None
    pct_ext = round((twi_ext / init_ext) * 100, 1) if twi_ext is not None and init_ext else None

    pcts = [p for p in [pct_int, pct_ci, pct_co, pct_ext] if p is not None]
    pct_avg = round(sum(pcts) / len(pcts), 1) if pcts else None

    return {
        'twi_int': twi_int, 'twi_ci': twi_ci, 'twi_co': twi_co, 'twi_ext': twi_ext,
        'twi_avg': twi_avg,
        'pct_int': pct_int, 'pct_ci': pct_ci, 'pct_co': pct_co, 'pct_ext': pct_ext,
        'pct_avg': pct_avg,
    }


def twi_pct(current_val, initial_val):
    if not initial_val or initial_val == 0:
        return 100.0
    return round((current_val / initial_val) * 100, 1)


def twi_color_class(pct):
    if pct >= 70:
        return 'twi-green'
    elif pct >= 40:
        return 'twi-yellow'
    elif pct >= 20:
        return 'twi-orange'
    return 'twi-red'


def twi_bg_color(pct):
    if pct >= 70:
        return '#16a34a'
    elif pct >= 40:
        return '#ca8a04'
    elif pct >= 20:
        return '#ea580c'
    return '#dc2626'


def save_photo(file_obj, team_id, tire_id):
    try:
        from PIL import Image
        import io

        upload_folder = current_app.config['UPLOAD_FOLDER']
        team_folder = os.path.join(upload_folder, str(team_id), str(tire_id))
        os.makedirs(team_folder, exist_ok=True)

        ext = os.path.splitext(file_obj.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            return None, None

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
        thumb_filename = f"thumb_{filename}"

        file_path = os.path.join(team_folder, filename)
        thumb_path = os.path.join(team_folder, thumb_filename)

        img = Image.open(file_obj)
        img.save(file_path)

        img.thumbnail((200, 200))
        img.save(thumb_path)

        rel_path = os.path.join('uploads', str(team_id), str(tire_id), filename)
        rel_thumb = os.path.join('uploads', str(team_id), str(tire_id), thumb_filename)

        return rel_path.replace('\\', '/'), rel_thumb.replace('\\', '/')
    except Exception:
        return None, None


def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles and 'superadmin' not in roles:
                if current_user.role != 'superadmin':
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_write(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_write:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def get_team_tracks(team_id):
    from app.models import Track
    return Track.query.filter(
        (Track.is_global == True) | (Track.team_id == team_id)
    ).order_by(Track.name).all()
