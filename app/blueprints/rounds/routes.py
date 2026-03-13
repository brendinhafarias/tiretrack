import json
from collections import defaultdict
from datetime import date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.blueprints.rounds import rounds_bp
from app.models import Round, Session, Tire, Driver, PitStop, PitStopChange
from app.extensions import db
from app.utils import get_team_tracks, require_write, calc_twi

_POS_ORDER = {'DE': 0, 'DD': 1, 'TE': 2, 'TD': 3}


@rounds_bp.route('/')
@login_required
def index():
    team_id = current_user.team_id
    open_rounds = Round.query.filter_by(team_id=team_id, status='open').order_by(Round.start_date.desc()).all()
    closed_rounds = Round.query.filter_by(team_id=team_id, status='closed').order_by(Round.start_date.desc()).all()
    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).all()
    tracks = get_team_tracks(team_id)

    # Count distinct event groups per round (matches detail page logic)
    all_round_ids = [r.id for r in open_rounds + closed_rounds]
    round_event_counts = {}
    if all_round_ids:
        from collections import defaultdict
        group_sets = defaultdict(set)
        all_sessions = Session.query.filter(
            Session.round_id.in_(all_round_ids)
        ).with_entities(Session.round_id, Session.set_id, Session.date, Session.event_type, Session.id).all()
        for s in all_sessions:
            key = (s.set_id, s.date.isoformat(), s.event_type) if s.set_id else ('solo', s.id)
            group_sets[s.round_id].add(key)
        round_event_counts = {rid: len(keys) for rid, keys in group_sets.items()}

    return render_template('rounds/index.html',
                           open_rounds=open_rounds,
                           closed_rounds=closed_rounds,
                           drivers=drivers,
                           tracks=tracks,
                           round_event_counts=round_event_counts)


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

    # Group sessions by tire (for "Estado dos Pneus" table)
    tire_sessions = {}
    for s in sessions:
        if s.tire_id not in tire_sessions:
            tire_sessions[s.tire_id] = {'tire': s.tire, 'sessions': []}
        tire_sessions[s.tire_id]['sessions'].append(s)

    for tid, data in tire_sessions.items():
        sorted_s = sorted(data['sessions'], key=lambda x: (x.date, x.created_at))
        data['first_session'] = sorted_s[0]
        data['last_session'] = sorted_s[-1]
        data['total_km'] = round(sum(s.km_session for s in data['sessions']), 1)
        data['total_laps'] = sum(s.laps for s in data['sessions'])

    # Build event groups: set sessions grouped by (set_id, date, event_type), solo per session
    set_groups = defaultdict(list)
    solo_list = []
    for s in sessions:
        if s.set_id:
            set_groups[(s.set_id, s.date.isoformat(), s.event_type)].append(s)
        else:
            solo_list.append(s)

    event_groups = []
    for (set_id, date_iso, etype), grp in set_groups.items():
        grp_sorted = sorted(grp, key=lambda x: _POS_ORDER.get(x.position, 99))
        first = grp_sorted[0]
        positions_data = [
            {
                'pos': s.position or '',
                'tire_code': s.tire.code,
                'twi_int': s.twi_int,
                'twi_ci': s.twi_ci,
                'twi_co': s.twi_co,
                'twi_ext': s.twi_ext,
                'twi_pct_avg': s.twi_pct_avg,
            }
            for s in grp_sorted
        ]
        pit_stop = PitStop.query.filter_by(
            set_id=set_id,
            date=date.fromisoformat(date_iso),
            event_type=etype,
            team_id=current_user.team_id,
        ).first()
        pit_stop_info = {'id': pit_stop.id, 'lap_stop': pit_stop.lap_stop} if pit_stop else None

        session_ids_str = ','.join(str(s.id) for s in grp_sorted)
        event_groups.append({
            'is_set': True,
            'tire_set': first.tire_set,
            'date': first.date,
            'event_type': first.event_type,
            'event_type_label': first.event_type_label,
            'track': first.track,
            'laps': first.laps,
            'km_session': first.km_session,
            'sessions': grp_sorted,
            'session_ids': session_ids_str,
            'edit_data': json.dumps({
                'session_ids': session_ids_str,
                'round_id': round_id,
                'date': first.date.isoformat(),
                'event_type': first.event_type,
                'laps': first.laps,
                'km_session': first.km_session,
                'is_set': True,
                'label': first.tire_set.name if first.tire_set else '—',
                'positions': positions_data,
                'pit_stop': pit_stop_info,
            }),
        })

    for s in solo_list:
        event_groups.append({
            'is_set': False,
            'tire_set': None,
            'date': s.date,
            'event_type': s.event_type,
            'event_type_label': s.event_type_label,
            'track': s.track,
            'laps': s.laps,
            'km_session': s.km_session,
            'sessions': [s],
            'session_ids': str(s.id),
            'edit_data': json.dumps({
                'session_ids': str(s.id),
                'round_id': round_id,
                'date': s.date.isoformat(),
                'event_type': s.event_type,
                'laps': s.laps,
                'km_session': s.km_session,
                'is_set': False,
                'label': s.tire.code,
                'positions': [{
                    'pos': s.position or '',
                    'tire_code': s.tire.code,
                    'twi_int': s.twi_int,
                    'twi_ci': s.twi_ci,
                    'twi_co': s.twi_co,
                    'twi_ext': s.twi_ext,
                    'twi_pct_avg': s.twi_pct_avg,
                }],
            }),
        })

    event_groups.sort(key=lambda x: (x['date'], x['sessions'][0].id))

    # Summary counts (deduplicated by event group)
    event_km = round(sum(eg['km_session'] for eg in event_groups), 1)
    event_laps = sum(eg['laps'] for eg in event_groups)
    event_count = len(event_groups)

    return render_template('rounds/detail.html',
                           rnd=rnd,
                           tire_sessions=list(tire_sessions.values()),
                           event_groups=event_groups,
                           event_km=event_km,
                           event_laps=event_laps,
                           event_count=event_count)


@rounds_bp.route('/<int:round_id>/sessions/group-edit', methods=['POST'])
@login_required
@require_write
def session_group_edit(round_id):
    from app.models import Session as SessionModel
    Round.query.filter_by(id=round_id, team_id=current_user.team_id).first_or_404()

    session_ids_raw = request.form.get('session_ids', '')
    try:
        session_ids = [int(x) for x in session_ids_raw.split(',') if x.strip()]
    except ValueError:
        flash('Dados inválidos.', 'error')
        return redirect(url_for('rounds.detail', round_id=round_id))

    sessions = SessionModel.query.filter(
        SessionModel.id.in_(session_ids),
        SessionModel.round_id == round_id,
        SessionModel.team_id == current_user.team_id
    ).all()

    if not sessions:
        flash('Sessões não encontradas.', 'error')
        return redirect(url_for('rounds.detail', round_id=round_id))

    new_event_type = request.form.get('event_type', '').strip()
    date_raw = request.form.get('date', '').strip()
    laps_raw = request.form.get('laps', '').strip()
    km_raw = request.form.get('km_session', '').strip()
    notes_common = request.form.get('notes', '').strip() or None

    for s in sessions:
        if new_event_type:
            s.event_type = new_event_type
        if date_raw:
            s.date = date.fromisoformat(date_raw)
        if laps_raw:
            s.laps = int(laps_raw)
        if km_raw:
            s.km_session = round(float(km_raw), 2)
        s.notes = notes_common

        pos = s.position
        if pos:
            twi_int_raw = request.form.get(f'{pos.lower()}_twi_int', '').strip()
            twi_ci_raw  = request.form.get(f'{pos.lower()}_twi_ci',  '').strip()
            twi_co_raw  = request.form.get(f'{pos.lower()}_twi_co',  '').strip()
            twi_ext_raw = request.form.get(f'{pos.lower()}_twi_ext', '').strip()
            tire = s.tire
            twi_data = calc_twi(twi_int_raw, twi_ci_raw, twi_co_raw, twi_ext_raw,
                                tire.twi_initial_int, tire.twi_initial_ci,
                                tire.twi_initial_co, tire.twi_initial_ext)

            if twi_data:
                s.twi_int = twi_data['twi_int']; s.twi_ci = twi_data['twi_ci']
                s.twi_co = twi_data['twi_co'];   s.twi_ext = twi_data['twi_ext']
                s.twi_avg = twi_data['twi_avg']
                s.twi_pct_int = twi_data['pct_int']; s.twi_pct_ci = twi_data['pct_ci']
                s.twi_pct_co = twi_data['pct_co'];   s.twi_pct_ext = twi_data['pct_ext']
                s.twi_pct_avg = twi_data['pct_avg']

                latest_twi = SessionModel.query.filter(
                    SessionModel.tire_id == tire.id,
                    SessionModel.twi_avg.isnot(None)
                ).order_by(SessionModel.date.desc(), SessionModel.id.desc()).first()
                if latest_twi and latest_twi.id == s.id:
                    tire.update_current_twi(twi_data['twi_int'], twi_data['twi_ci'],
                                            twi_data['twi_co'], twi_data['twi_ext'])

    # Update associated pit stop if lap_stop provided
    first_s = sessions[0]
    if first_s.set_id:
        pit_stop = PitStop.query.filter_by(
            set_id=first_s.set_id,
            date=first_s.date,
            event_type=first_s.event_type,
            team_id=current_user.team_id,
        ).first()
        if pit_stop:
            lap_stop_raw = request.form.get('lap_stop', '').strip()
            if lap_stop_raw:
                pit_stop.lap_stop = int(lap_stop_raw)
            if date_raw:
                pit_stop.date = date.fromisoformat(date_raw)
            if new_event_type:
                pit_stop.event_type = new_event_type

    db.session.commit()
    flash('Sessão atualizada.', 'success')
    return redirect(url_for('rounds.detail', round_id=round_id))


@rounds_bp.route('/<int:round_id>/sessions/group-delete', methods=['POST'])
@login_required
@require_write
def session_group_delete(round_id):
    from app.models import Session as SessionModel
    Round.query.filter_by(id=round_id, team_id=current_user.team_id).first_or_404()

    session_ids_raw = request.form.get('session_ids', '')
    try:
        session_ids = [int(x) for x in session_ids_raw.split(',') if x.strip()]
    except ValueError:
        flash('Dados inválidos.', 'error')
        return redirect(url_for('rounds.detail', round_id=round_id))

    sessions = SessionModel.query.filter(
        SessionModel.id.in_(session_ids),
        SessionModel.round_id == round_id,
        SessionModel.team_id == current_user.team_id
    ).all()

    if not sessions:
        flash('Sessões não encontradas.', 'error')
        return redirect(url_for('rounds.detail', round_id=round_id))

    # Update tire totals and revert TWI
    for s in sessions:
        tire = s.tire
        if tire:
            tire.total_km = max(0, round((tire.total_km or 0) - (s.km_session or 0), 3))
            tire.total_laps = max(0, (tire.total_laps or 0) - (s.laps or 0))

    # Revert TWI to most recent remaining session per tire
    affected_tire_ids = {s.tire_id for s in sessions if s.tire_id}
    for tid in affected_tire_ids:
        tire = Tire.query.get(tid)
        if not tire:
            continue
        latest = SessionModel.query.filter(
            SessionModel.tire_id == tid,
            SessionModel.twi_avg.isnot(None),
            ~SessionModel.id.in_(session_ids)
        ).order_by(SessionModel.date.desc(), SessionModel.id.desc()).first()
        if latest:
            tire.update_current_twi(latest.twi_int, latest.twi_ci,
                                    latest.twi_co, latest.twi_ext)
        else:
            # No remaining sessions — reset to initial values
            tire.current_twi_int = tire.twi_initial_int
            tire.current_twi_ci  = tire.twi_initial_ci
            tire.current_twi_co  = tire.twi_initial_co
            tire.current_twi_ext = tire.twi_initial_ext
            inits = [tire.twi_initial_int, tire.twi_initial_ci,
                     tire.twi_initial_co, tire.twi_initial_ext]
            tire.current_twi_avg = round(sum(inits) / 4, 2) if all(inits) else None
            tire.current_twi_pct = 100.0

    # Delete associated pit stop (and its changes) if any
    first_s = sessions[0]
    if first_s.set_id:
        pit_stop = PitStop.query.filter_by(
            set_id=first_s.set_id,
            date=first_s.date,
            event_type=first_s.event_type,
            team_id=current_user.team_id,
        ).first()
        if pit_stop:
            for change in pit_stop.changes:
                db.session.delete(change)
            db.session.delete(pit_stop)

    for s in sessions:
        db.session.delete(s)

    db.session.commit()
    flash('Sessão apagada.', 'success')
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
