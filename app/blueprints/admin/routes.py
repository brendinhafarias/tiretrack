from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.models import Team, User, Driver, Track
from app.extensions import db


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_team_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@require_admin
def index():
    team_id = current_user.team_id

    if current_user.is_superadmin:
        teams = Team.query.order_by(Team.name).all()
        users = User.query.order_by(User.username).all()
        tracks = Track.query.filter_by(is_global=True).order_by(Track.name).all()
        return render_template('admin/superadmin.html', teams=teams, users=users, tracks=tracks)

    # team_admin view
    users = User.query.filter_by(team_id=team_id).order_by(User.username).all()
    drivers = Driver.query.filter_by(team_id=team_id).order_by(Driver.name).all()
    tracks = Track.query.filter(
        (Track.is_global == True) | (Track.team_id == team_id)
    ).order_by(Track.name).all()
    team = current_user.team

    return render_template('admin/index.html',
                           users=users,
                           drivers=drivers,
                           tracks=tracks,
                           team=team)


# ---- Teams (superadmin only) ----

@admin_bp.route('/teams/new', methods=['POST'])
@login_required
def team_new():
    if not current_user.is_superadmin:
        abort(403)

    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip().lower().replace(' ', '-')

    if not name or not slug:
        flash('Preencha nome e slug da equipe.', 'error')
        return redirect(url_for('admin.index'))

    if Team.query.filter_by(slug=slug).first():
        flash('Slug já existe.', 'error')
        return redirect(url_for('admin.index'))

    team = Team(name=name, slug=slug)
    db.session.add(team)
    db.session.commit()
    flash(f'Equipe {name} criada!', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/teams/<int:team_id>/toggle', methods=['POST'])
@login_required
def team_toggle(team_id):
    if not current_user.is_superadmin:
        abort(403)
    team = Team.query.get_or_404(team_id)
    team.is_active = not team.is_active
    db.session.commit()
    status = 'ativada' if team.is_active else 'desativada'
    flash(f'Equipe {team.name} {status}.', 'success')
    return redirect(url_for('admin.index'))


# ---- Users ----

@admin_bp.route('/users/new', methods=['POST'])
@login_required
@require_admin
def user_new():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'team_user')
    team_id_form = request.form.get('team_id')

    if current_user.is_superadmin:
        team_id = int(team_id_form) if team_id_form else None
    else:
        team_id = current_user.team_id
        if role == 'superadmin':
            abort(403)

    if not username or not email or not password:
        flash('Preencha todos os campos do usuário.', 'error')
        return redirect(url_for('admin.index'))

    if User.query.filter_by(username=username).first():
        flash('Username já existe.', 'error')
        return redirect(url_for('admin.index'))

    user = User(username=username, email=email, role=role, team_id=team_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'Usuário {username} criado!', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@require_admin
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if not current_user.is_superadmin and user.team_id != current_user.team_id:
        abort(403)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'Usuário {user.username} {"ativado" if user.is_active else "desativado"}.', 'success')
    return redirect(url_for('admin.index'))


# ---- Drivers ----

@admin_bp.route('/drivers/new', methods=['POST'])
@login_required
@require_admin
def driver_new():
    name = request.form.get('name', '').strip()
    number = request.form.get('number', '').strip()
    category = request.form.get('category', '').strip()
    team_id = current_user.team_id

    if current_user.is_superadmin:
        tid = request.form.get('team_id')
        team_id = int(tid) if tid else None

    if not name:
        flash('Informe o nome do piloto.', 'error')
        return redirect(url_for('admin.index'))

    driver = Driver(team_id=team_id, name=name, number=number, category=category)
    db.session.add(driver)
    db.session.commit()
    flash(f'Piloto {name} cadastrado!', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/drivers/<int:driver_id>/toggle', methods=['POST'])
@login_required
@require_admin
def driver_toggle(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    if not current_user.is_superadmin and driver.team_id != current_user.team_id:
        abort(403)
    driver.is_active = not driver.is_active
    db.session.commit()
    flash(f'Piloto {driver.name} {"ativado" if driver.is_active else "desativado"}.', 'success')
    return redirect(url_for('admin.index'))


# ---- Tracks ----

@admin_bp.route('/tracks/new', methods=['POST'])
@login_required
@require_admin
def track_new():
    name = request.form.get('name', '').strip()
    km_per_lap = request.form.get('km_per_lap')
    location = request.form.get('location', '').strip()
    is_global = request.form.get('is_global') == 'on'

    if not name:
        flash('Informe o nome da pista.', 'error')
        return redirect(url_for('admin.index'))

    team_id = None if is_global else current_user.team_id
    if not current_user.is_superadmin:
        is_global = False
        team_id = current_user.team_id

    track = Track(
        name=name,
        km_per_lap=float(km_per_lap) if km_per_lap else None,
        location=location,
        is_global=is_global,
        team_id=team_id
    )
    db.session.add(track)
    db.session.commit()
    flash(f'Pista {name} cadastrada!', 'success')
    return redirect(url_for('admin.index'))
