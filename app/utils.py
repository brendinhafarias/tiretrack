import os
import uuid
from datetime import datetime
from functools import wraps
from flask import abort, current_app
from flask_login import current_user


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
