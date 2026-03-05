from datetime import date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.blueprints.rounds import rounds_bp
from app.models import Round, Session, Tire, Driver
from app.extensions import db
from app.utils import get_team_tracks, require_write


@rounds_bp.route('/')
@login_required
def index():
    team_id = current_user.team_id
    open_rounds = Round.query.filter_by(team_id=team_id, status='open').order_by(Round.start_date.desc()).all()
    closed_rounds = Round.query.filter_by(team_id=team_id, status='closed').order_by(Round.start_date.desc()).all()
    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).all()
    tracks = get_team_tracks(team_id)

    return render_template('rounds/index.html',
                           open_rounds=open_rounds,
                           closed_rounds=closed_rounds,
                           drivers=drivers,
                           tracks=tracks)


@rounds_bp.route('/new', methods=['POST'])
@login_required
@require_write
def new():
    team_id = current_user.team_id
    name = request.form.get('name', '').strip()
    driver_id = int(request.form.get('driver_id'))
    track_id = request.form.get('track_id') or None
    start_date = request.form.get('start_date') or None
    end_date = request.form.get('end_date') or None

    if not name:
        flash('Informe o nome da etapa.', 'error')
        return redirect(url_for('rounds.index'))

    rnd = Round(
        team_id=team_id,
        driver_id=driver_id,
        track_id=int(track_id) if track_id else None,
        name=name,
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        status='open'
    )
    db.session.add(rnd)
    db.session.commit()
    flash(f'Etapa "{name}" criada!', 'success')
    return redirect(url_for('rounds.detail', round_id=rnd.id))


@rounds_bp.route('/<int:round_id>')
@login_required
def detail(round_id):
    rnd = Round.query.filter_by(id=round_id, team_id=current_user.team_id).first_or_404()
    sessions = Session.query.filter_by(round_id=round_id).order_by(Session.date, Session.created_at).all()

    # Group sessions by tire
    tire_sessions = {}
    for s in sessions:
        if s.tire_id not in tire_sessions:
            tire_sessions[s.tire_id] = {'tire': s.tire, 'sessions': []}
        tire_sessions[s.tire_id]['sessions'].append(s)

    # Compute aggregates per tire in round
    for tid, data in tire_sessions.items():
        sorted_s = sorted(data['sessions'], key=lambda x: (x.date, x.created_at))
        data['first_session'] = sorted_s[0]
        data['last_session'] = sorted_s[-1]
        data['total_km'] = round(sum(s.km_session for s in data['sessions']), 1)
        data['total_laps'] = sum(s.laps for s in data['sessions'])

    # Deduplicate events for summary: set sessions grouped by (set_id, date, event_type); solo by tire
    seen_event_keys = set()
    event_km = 0.0
    event_laps = 0
    event_count = 0
    for s in sessions:
        key = ('set', s.set_id, s.date, s.event_type) if s.set_id else ('tire', s.tire_id, s.date, s.event_type)
        if key not in seen_event_keys:
            seen_event_keys.add(key)
            event_km += s.km_session
            event_laps += s.laps
            event_count += 1

    return render_template('rounds/detail.html',
                           rnd=rnd,
                           sessions=sessions,
                           tire_sessions=list(tire_sessions.values()),
                           event_km=round(event_km, 1),
                           event_laps=event_laps,
                           event_count=event_count)


@rounds_bp.route('/<int:round_id>/close', methods=['POST'])
@login_required
@require_write
def close(round_id):
    rnd = Round.query.filter_by(id=round_id, team_id=current_user.team_id).first_or_404()

    # Get all tire IDs used in this round
    round_tire_ids = [s.tire_id for s in db.session.query(Session.tire_id).filter_by(
        round_id=round_id, team_id=current_user.team_id
    ).distinct().all()]

    # IDs the user wants to KEEP for next round
    keep_ids = [int(x) for x in request.form.getlist('keep_tire_ids')]

    # Mark non-kept tires as trash
    discarded = 0
    for tid in round_tire_ids:
        if tid not in keep_ids:
            tire = Tire.query.filter_by(id=tid, team_id=current_user.team_id).first()
            if tire and tire.status != 'trash':
                tire.status = 'trash'
                discarded += 1

    rnd.status = 'closed'
    db.session.commit()

    msg = f'Etapa "{rnd.name}" encerrada.'
    if discarded:
        msg += f' {discarded} pneu(s) descartado(s).'
    if keep_ids:
        msg += f' {len(keep_ids)} pneu(s) mantido(s).'
    flash(msg, 'success')
    return redirect(url_for('rounds.detail', round_id=round_id))
