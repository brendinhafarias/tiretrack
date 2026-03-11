from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.blueprints.tires import tires_bp
from app.models import Tire, Session, Observation, Driver, Track, Round, TireSet, TirePhoto
from app.extensions import db
from app.utils import save_photo, get_team_tracks, require_write


@tires_bp.route('/new', methods=['GET', 'POST'])
@login_required
@require_write
def new():
    team_id = current_user.team_id
    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).all()
    rounds = Round.query.filter_by(team_id=team_id, status='open').order_by(Round.name).all()

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        barcode = request.form.get('barcode', '').strip() or None
        driver_id = int(request.form.get('driver_id'))
        tire_type = request.form.get('tire_type', 'slick')
        round_id = request.form.get('round_id') or None
        km_initial = float(request.form.get('km_initial', 0))

        twi_int = float(request.form.get('twi_int'))
        twi_ci = float(request.form.get('twi_ci'))
        twi_co = float(request.form.get('twi_co'))
        twi_ext = float(request.form.get('twi_ext'))

        # Validate uniqueness within team
        existing = Tire.query.filter_by(team_id=team_id, code=code).first()
        if existing:
            flash(f'Código {code} já existe nesta equipe.', 'error')
            return render_template('tires/new.html', drivers=drivers, rounds=rounds)

        tire = Tire(
            team_id=team_id,
            driver_id=driver_id,
            round_id=int(round_id) if round_id else None,
            code=code,
            barcode=barcode,
            tire_type=tire_type,
            km_initial=km_initial,
            total_km=km_initial,
            total_laps=0,
            twi_initial_int=twi_int,
            twi_initial_ci=twi_ci,
            twi_initial_co=twi_co,
            twi_initial_ext=twi_ext,
            current_twi_int=twi_int,
            current_twi_ci=twi_ci,
            current_twi_co=twi_co,
            current_twi_ext=twi_ext,
            current_twi_avg=round((twi_int + twi_ci + twi_co + twi_ext) / 4, 2),
            current_twi_pct=100.0,
            status='available'
        )
        db.session.add(tire)
        db.session.flush()  # get tire.id before commit

        for photo_file in request.files.getlist('photos'):
            if photo_file and photo_file.filename:
                rel_path, rel_thumb = save_photo(photo_file, team_id, tire.id)
                db.session.add(TirePhoto(team_id=team_id, tire_id=tire.id, path=rel_path, thumb_path=rel_thumb))

        db.session.commit()

        flash(f'Pneu {code} cadastrado com sucesso!', 'success')
        return redirect(url_for('tires.detail', tire_id=tire.id))

    return render_template('tires/new.html', drivers=drivers, rounds=rounds)


@tires_bp.route('/<int:tire_id>')
@login_required
def detail(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()
    sessions = Session.query.filter_by(tire_id=tire_id).order_by(Session.date.desc()).all()
    observations = Observation.query.filter_by(tire_id=tire_id).order_by(Observation.created_at.desc()).all()

    active_set = tire.get_active_set()
    position = tire.get_position_in_set(active_set) if active_set else None
    tracks = tire.get_tracks_used()

    # TWI Profile Chart: one line per session (up to 5 most recent), x=position, y=mm
    profile_sessions = sessions[:5][::-1]  # up to 5, oldest first
    chart_profiles = [
        {
            'label': s.date.strftime('%d/%m/%y') + f' · {s.event_type_label}',
            'values': [s.twi_int, s.twi_ci, s.twi_co, s.twi_ext]
        }
        for s in profile_sessions
    ]
    chart_initial = [
        tire.twi_initial_int, tire.twi_initial_ci,
        tire.twi_initial_co, tire.twi_initial_ext
    ]

    # Km by track
    from app.models import Track as TrackModel
    from sqlalchemy import func
    km_by_track_raw = db.session.query(
        TrackModel.name,
        func.sum(Session.km_session)
    ).join(Session, Session.track_id == TrackModel.id).filter(
        Session.tire_id == tire_id
    ).group_by(TrackModel.name).all()
    km_by_track = [[name, round(float(km), 1)] for name, km in km_by_track_raw]

    return render_template('tires/detail.html',
                           tire=tire,
                           sessions=sessions,
                           observations=observations,
                           active_set=active_set,
                           position=position,
                           tracks=tracks,
                           chart_profiles=chart_profiles,
                           chart_initial=chart_initial,
                           km_by_track=km_by_track)


@tires_bp.route('/<int:tire_id>/session/new', methods=['GET', 'POST'])
@login_required
@require_write
def session_new(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()
    team_id = current_user.team_id
    tracks = get_team_tracks(team_id)
    rounds = Round.query.filter_by(team_id=team_id, status='open').order_by(Round.name).all()

    if request.method == 'POST':
        track_id = int(request.form.get('track_id'))
        round_id = request.form.get('round_id') or None
        event_type = request.form.get('event_type', 'practice')
        position = request.form.get('position', '')
        session_date = date.fromisoformat(request.form.get('date', date.today().isoformat()))
        laps = int(request.form.get('laps'))
        km_manual = request.form.get('km_manual')

        twi_int = float(request.form.get('twi_int'))
        twi_ci = float(request.form.get('twi_ci'))
        twi_co = float(request.form.get('twi_co'))
        twi_ext = float(request.form.get('twi_ext'))
        notes = request.form.get('notes', '').strip() or None

        track = Track.query.get(track_id)
        if track and track.km_per_lap:
            km_session = round(laps * track.km_per_lap, 3)
        else:
            km_session = float(km_manual or 0)

        km_cumulative = tire.total_km + km_session
        twi_avg = round((twi_int + twi_ci + twi_co + twi_ext) / 4, 2)

        pct_int = round((twi_int / tire.twi_initial_int) * 100, 1) if tire.twi_initial_int else 100
        pct_ci = round((twi_ci / tire.twi_initial_ci) * 100, 1) if tire.twi_initial_ci else 100
        pct_co = round((twi_co / tire.twi_initial_co) * 100, 1) if tire.twi_initial_co else 100
        pct_ext = round((twi_ext / tire.twi_initial_ext) * 100, 1) if tire.twi_initial_ext else 100
        pct_avg = round((pct_int + pct_ci + pct_co + pct_ext) / 4, 1)

        # Find active set for this tire
        active_set = tire.get_active_set()

        session = Session(
            team_id=team_id,
            tire_id=tire.id,
            set_id=active_set.id if active_set else None,
            round_id=int(round_id) if round_id else None,
            track_id=track_id,
            driver_id=tire.driver_id,
            event_type=event_type,
            position=position,
            date=session_date,
            laps=laps,
            km_session=km_session,
            km_cumulative=km_cumulative,
            twi_int=twi_int,
            twi_ci=twi_ci,
            twi_co=twi_co,
            twi_ext=twi_ext,
            twi_avg=twi_avg,
            twi_pct_int=pct_int,
            twi_pct_ci=pct_ci,
            twi_pct_co=pct_co,
            twi_pct_ext=pct_ext,
            twi_pct_avg=pct_avg,
            notes=notes
        )
        db.session.add(session)

        # Update tire current state
        tire.total_km = km_cumulative
        tire.total_laps = (tire.total_laps or 0) + laps
        tire.update_current_twi(twi_int, twi_ci, twi_co, twi_ext)

        db.session.commit()
        flash(f'Sessão registrada! TWI médio: {twi_avg:.1f}mm ({pct_avg:.0f}% restante)', 'success')
        return redirect(url_for('tires.detail', tire_id=tire.id))

    return render_template('tires/session_new.html', tire=tire, tracks=tracks, rounds=rounds)


@tires_bp.route('/<int:tire_id>/observation/new', methods=['POST'])
@login_required
@require_write
def observation_new(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()

    text = request.form.get('text', '').strip()
    action = request.form.get('action', 'ok')

    if not text:
        flash('Digite o texto da observação.', 'error')
        return redirect(url_for('tires.detail', tire_id=tire_id, tab='observations'))

    photo_path = None
    photo_thumb = None
    photo_file = request.files.get('photo')
    if photo_file and photo_file.filename:
        photo_path, photo_thumb = save_photo(photo_file, tire.team_id, tire.id)

    obs = Observation(
        team_id=tire.team_id,
        tire_id=tire.id,
        author_id=current_user.id,
        text=text,
        action=action,
        photo_path=photo_path,
        photo_thumb_path=photo_thumb
    )
    db.session.add(obs)

    # Apply status changes based on action
    if action == 'block':
        tire.status = 'blocked'
        flash(f'Pneu {tire.code} bloqueado.', 'warning')
    elif action == 'discard':
        tire.status = 'trash'
        flash(f'Pneu {tire.code} descartado.', 'warning')
    elif action == 'release' and tire.status == 'blocked':
        tire.status = 'available'
        flash(f'Pneu {tire.code} liberado.', 'success')

    db.session.commit()
    if action not in ('block', 'discard', 'release'):
        flash('Observação registrada.', 'success')

    return redirect(url_for('tires.detail', tire_id=tire_id, tab='observations'))


@tires_bp.route('/<int:tire_id>/observation/<int:obs_id>/delete', methods=['POST'])
@login_required
@require_write
def observation_delete(tire_id, obs_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()
    obs = Observation.query.filter_by(id=obs_id, tire_id=tire_id, team_id=current_user.team_id).first_or_404()
    db.session.delete(obs)
    db.session.flush()

    # Recalculate tire status from most recent remaining observation
    latest = Observation.query.filter_by(tire_id=tire_id, team_id=current_user.team_id)\
        .order_by(Observation.created_at.desc()).first()
    if latest and latest.action == 'block':
        tire.status = 'blocked'
    elif latest and latest.action == 'discard':
        tire.status = 'trash'
    else:
        # No status-changing observation remains; restore to available unless mounted in an active set
        if tire.status in ('blocked', 'trash'):
            tire.status = 'mounted' if tire.get_active_set() else 'available'

    db.session.commit()
    flash('Observação removida.', 'success')
    return redirect(url_for('tires.detail', tire_id=tire_id, tab='observations'))


@tires_bp.route('/<int:tire_id>/delete', methods=['POST'])
@login_required
@require_write
def delete(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()

    if not current_user.is_team_admin:
        abort(403)

    code = tire.code

    # Remove all child records first (no cascade configured in models)
    Session.query.filter_by(tire_id=tire_id).delete()
    Observation.query.filter_by(tire_id=tire_id).delete()
    TirePhoto.query.filter_by(tire_id=tire_id).delete()

    # Remove from any active set positions
    if tire.status == 'mounted':
        active_set = tire.get_active_set()
        if active_set:
            for pos in ('tire_de_id', 'tire_dd_id', 'tire_te_id', 'tire_td_id'):
                if getattr(active_set, pos) == tire_id:
                    setattr(active_set, pos, None)

    db.session.delete(tire)
    db.session.commit()

    flash(f'Pneu {code} removido com sucesso.', 'success')
    return redirect(url_for('dashboard.index'))


@tires_bp.route('/<int:tire_id>/status', methods=['POST'])
@login_required
@require_write
def change_status(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first_or_404()
    new_status = request.form.get('status')

    if new_status == 'trash':
        confirm = request.form.get('confirm_discard')
        if not confirm:
            flash('Confirmação necessária para descartar.', 'error')
            return redirect(url_for('tires.detail', tire_id=tire_id))

    allowed = ['available', 'blocked', 'trash']
    if new_status in allowed:
        tire.status = new_status
        db.session.commit()
        flash(f'Status do pneu {tire.code} atualizado para {new_status}.', 'success')

    return redirect(url_for('tires.detail', tire_id=tire_id))
