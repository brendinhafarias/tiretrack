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


@rounds_bp.route('/<int:round_id>/sessions/<int:session_id>/edit', methods=['POST'])
@login_required
@require_write
def session_edit(round_id, session_id):
    from app.models import Session as SessionModel
    rnd = Round.query.filter_by(id=round_id, team_id=current_user.team_id).first_or_404()
    session = SessionModel.query.filter_by(
        id=session_id, round_id=round_id, team_id=current_user.team_id
    ).first_or_404()
    tire = session.tire

    session.event_type = request.form.get('event_type', session.event_type)
    session.position   = request.form.get('position', '').strip() or session.position
    session.notes      = request.form.get('notes', '').strip() or None

    date_raw = request.form.get('date', '').strip()
    if date_raw:
        session.date = date.fromisoformat(date_raw)

    twi_int_raw = request.form.get('twi_int', '').strip()
    twi_ci_raw  = request.form.get('twi_ci',  '').strip()
    twi_co_raw  = request.form.get('twi_co',  '').strip()
    twi_ext_raw = request.form.get('twi_ext', '').strip()
    has_twi = all([twi_int_raw, twi_ci_raw, twi_co_raw, twi_ext_raw])

    if has_twi:
        twi_int = float(twi_int_raw)
        twi_ci  = float(twi_ci_raw)
        twi_co  = float(twi_co_raw)
        twi_ext = float(twi_ext_raw)
        twi_avg = round((twi_int + twi_ci + twi_co + twi_ext) / 4, 2)
        pct_int = round((twi_int / tire.twi_initial_int) * 100, 1) if tire.twi_initial_int else 100
        pct_ci  = round((twi_ci  / tire.twi_initial_ci)  * 100, 1) if tire.twi_initial_ci  else 100
        pct_co  = round((twi_co  / tire.twi_initial_co)  * 100, 1) if tire.twi_initial_co  else 100
        pct_ext = round((twi_ext / tire.twi_initial_ext) * 100, 1) if tire.twi_initial_ext else 100
        pct_avg = round((pct_int + pct_ci + pct_co + pct_ext) / 4, 1)

        session.twi_int     = twi_int
        session.twi_ci      = twi_ci
        session.twi_co      = twi_co
        session.twi_ext     = twi_ext
        session.twi_avg     = twi_avg
        session.twi_pct_int = pct_int
        session.twi_pct_ci  = pct_ci
        session.twi_pct_co  = pct_co
        session.twi_pct_ext = pct_ext
        session.twi_pct_avg = pct_avg

        # Update tire current TWI if this is the most recent session with TWI for this tire
        latest_twi = SessionModel.query.filter(
            SessionModel.tire_id == tire.id,
            SessionModel.twi_avg.isnot(None)
        ).order_by(SessionModel.date.desc(), SessionModel.id.desc()).first()
        if latest_twi and latest_twi.id == session.id:
            tire.update_current_twi(twi_int, twi_ci, twi_co, twi_ext)

    db.session.commit()
    flash('Sessão atualizada.', 'success')
    return redirect(url_for('rounds.detail', round_id=round_id))


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
