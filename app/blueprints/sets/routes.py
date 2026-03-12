import json
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.blueprints.sets import sets_bp
from app.models import TireSet, Tire, Driver, PitStop, PitStopChange
from app.extensions import db
from app.utils import require_write, calc_twi


@sets_bp.route('/')
@login_required
def index():
    team_id = current_user.team_id
    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).all()
    driver_id = request.args.get('driver_id', type=int)

    q_active = TireSet.query.filter_by(team_id=team_id, status='active')
    q_dismounted = TireSet.query.filter_by(team_id=team_id, status='dismounted')

    if driver_id:
        q_active = q_active.filter_by(driver_id=driver_id)
        q_dismounted = q_dismounted.filter_by(driver_id=driver_id)

    active_sets = q_active.order_by(TireSet.created_at.desc()).all()
    dismounted_sets = q_dismounted.order_by(TireSet.dismounted_at.desc()).limit(10).all()

    available_tires = Tire.query.filter_by(team_id=team_id).filter(Tire.status != 'trash').order_by(Tire.code).all()

    return render_template('sets/index.html',
                           active_sets=active_sets,
                           dismounted_sets=dismounted_sets,
                           available_tires=available_tires,
                           drivers=drivers,
                           selected_driver=driver_id)


@sets_bp.route('/new', methods=['POST'])
@login_required
@require_write
def new():
    team_id = current_user.team_id
    name = request.form.get('name', '').strip()
    driver_id = int(request.form.get('driver_id'))
    tire_de_id = request.form.get('tire_de_id')
    tire_dd_id = request.form.get('tire_dd_id')
    tire_te_id = request.form.get('tire_te_id')
    tire_td_id = request.form.get('tire_td_id')

    if not name:
        flash('Informe o nome do set.', 'error')
        return redirect(url_for('sets.index'))

    if not all([tire_de_id, tire_dd_id, tire_te_id, tire_td_id]):
        flash('Selecione os 4 pneus para montar o set.', 'error')
        return redirect(url_for('sets.index'))

    ids = [int(tire_de_id), int(tire_dd_id), int(tire_te_id), int(tire_td_id)]

    if len(ids) != len(set(ids)):
        flash('Erro: o mesmo pneu não pode ocupar mais de uma posição.', 'error')
        return redirect(url_for('sets.index'))

    # Validate tires belong to team and are not discarded
    for tid in ids:
        tire = Tire.query.filter_by(id=tid, team_id=team_id).first()
        if not tire:
            flash('Pneu inválido.', 'error')
            return redirect(url_for('sets.index'))
        if tire.status == 'trash':
            flash(f'Pneu {tire.code} está descartado e não pode ser montado.', 'error')
            return redirect(url_for('sets.index'))

    tire_set = TireSet(
        team_id=team_id,
        driver_id=driver_id,
        name=name,
        status='active',
        tire_de_id=ids[0],
        tire_dd_id=ids[1],
        tire_te_id=ids[2],
        tire_td_id=ids[3]
    )
    db.session.add(tire_set)

    # Update tire statuses to mounted
    for tid in ids:
        tire = Tire.query.get(tid)
        if tire:
            tire.status = 'mounted'

    db.session.commit()
    flash(f'Set "{name}" montado com sucesso!', 'success')
    return redirect(url_for('sets.index'))


@sets_bp.route('/<int:set_id>/dismantle', methods=['POST'])
@login_required
@require_write
def dismantle(set_id):
    tire_set = TireSet.query.filter_by(id=set_id, team_id=current_user.team_id).first_or_404()

    if tire_set.status != 'active':
        flash('Set já está desmontado.', 'error')
        return redirect(url_for('sets.index'))

    tire_set.status = 'dismounted'
    tire_set.dismounted_at = datetime.utcnow()

    # Restore tire statuses (keep blocked/trash as-is)
    for tire in [tire_set.tire_de, tire_set.tire_dd, tire_set.tire_te, tire_set.tire_td]:
        if tire and tire.status == 'mounted':
            tire.status = 'available'

    db.session.commit()
    flash(f'Set "{tire_set.name}" desmontado. Pneus liberados.', 'success')
    return redirect(url_for('sets.index'))


@sets_bp.route('/<int:set_id>/swap', methods=['POST'])
@login_required
@require_write
def swap(set_id):
    tire_set = TireSet.query.filter_by(id=set_id, team_id=current_user.team_id).first_or_404()

    if tire_set.status != 'active':
        flash('Só é possível trocar pneus em sets ativos.', 'error')
        return redirect(url_for('sets.index'))

    position = request.form.get('position')  # DE, DD, TE, TD
    new_tire_id = request.form.get('new_tire_id', type=int)

    if not position or not new_tire_id:
        flash('Selecione a posição e o novo pneu.', 'error')
        return redirect(url_for('sets.index'))

    new_tire = Tire.query.filter_by(id=new_tire_id, team_id=current_user.team_id).first()
    if not new_tire or new_tire.status == 'trash':
        flash('Pneu selecionado inválido ou descartado.', 'error')
        return redirect(url_for('sets.index'))

    # Free old tire
    pos_map = {
        'DE': ('tire_de_id', tire_set.tire_de),
        'DD': ('tire_dd_id', tire_set.tire_dd),
        'TE': ('tire_te_id', tire_set.tire_te),
        'TD': ('tire_td_id', tire_set.tire_td),
    }

    if position not in pos_map:
        flash('Posição inválida.', 'error')
        return redirect(url_for('sets.index'))

    field, old_tire = pos_map[position]

    # Free old tire
    if old_tire and old_tire.status == 'mounted':
        old_tire.status = 'available'

    setattr(tire_set, field, new_tire.id)
    new_tire.status = 'mounted'

    db.session.commit()
    flash(f'Posição {position} trocada para pneu {new_tire.code}.', 'success')
    return redirect(url_for('sets.index'))


@sets_bp.route('/<int:set_id>/session/new', methods=['GET', 'POST'])
@login_required
@require_write
def session_new(set_id):
    from app.models import Session, Round, Track
    from app.utils import get_team_tracks
    from datetime import date as date_cls

    tire_set = TireSet.query.filter_by(id=set_id, team_id=current_user.team_id).first_or_404()
    if tire_set.status != 'active':
        flash('Só é possível registrar sessões em sets ativos.', 'error')
        return redirect(url_for('sets.index'))

    team_id = current_user.team_id
    tracks = get_team_tracks(team_id)
    rounds = Round.query.filter_by(team_id=team_id, status='open').order_by(Round.name).all()
    available_tires = Tire.query.filter_by(team_id=team_id, status='available').order_by(Tire.code).all()
    available_tires_json = json.dumps({
        t.id: {
            'code': t.code,
            'compound': t.compound or '',
            'total_km': t.total_km or 0,
            'total_laps': t.total_laps or 0,
            'pct': t.current_twi_pct or 100,
            'twi_int': t.current_twi_int,
            'twi_ci':  t.current_twi_ci,
            'twi_co':  t.current_twi_co,
            'twi_ext': t.current_twi_ext,
            'init_int': t.twi_initial_int,
            'init_ci':  t.twi_initial_ci,
            'init_co':  t.twi_initial_co,
            'init_ext': t.twi_initial_ext,
        }
        for t in available_tires
    })

    positions_tires = [
        ('DE', tire_set.tire_de),
        ('DD', tire_set.tire_dd),
        ('TE', tire_set.tire_te),
        ('TD', tire_set.tire_td),
    ]
    tire_initials_json = json.dumps({
        pos: {'int': t.twi_initial_int, 'ci': t.twi_initial_ci, 'co': t.twi_initial_co, 'ext': t.twi_initial_ext}
        for pos, t in positions_tires if t
    })

    # Detect tires recently swapped in (no session after swap) for automatic lap adjustment
    recent_pit = PitStop.query.filter_by(set_id=tire_set.id, team_id=team_id).order_by(PitStop.id.desc()).first()
    pit_swap_info = {}  # {tire_id: lap_stop}
    if recent_pit:
        for change in recent_pit.changes:
            if Session.query.filter(Session.tire_id == change.tire_in_id, Session.laps > 0).count() == 0:
                pit_swap_info[change.tire_in_id] = recent_pit.lap_stop

    pos_field_map = {
        'DE': 'tire_de_id',
        'DD': 'tire_dd_id',
        'TE': 'tire_te_id',
        'TD': 'tire_td_id',
    }

    if request.method == 'POST':
        track_id = int(request.form.get('track_id'))
        round_id = request.form.get('round_id') or None
        event_type = request.form.get('event_type', 'practice')
        session_date = date_cls.fromisoformat(request.form.get('date', date_cls.today().isoformat()))
        laps = int(request.form.get('laps'))
        km_manual = request.form.get('km_manual')

        track = Track.query.get(track_id)
        km_per_lap = track.km_per_lap if track and track.km_per_lap else None
        km_session = round(laps * km_per_lap, 3) if km_per_lap else float(km_manual or 0)

        # Pit stop handling
        has_pitstop = request.form.get('has_pitstop') == '1'
        lap_stop = None
        km_stint = None
        pit_stop_obj = None

        if has_pitstop:
            lap_stop_raw = request.form.get('lap_stop', '').strip()
            if not lap_stop_raw or int(lap_stop_raw) <= 0:
                flash('Informe a volta do pit stop.', 'error')
                return redirect(url_for('sets.session_new', set_id=set_id))
            lap_stop = int(lap_stop_raw)
            km_stint = round(lap_stop * km_per_lap, 3) if km_per_lap else float(request.form.get('km_stint_manual') or 0)

            pit_stop_obj = PitStop(
                team_id=team_id,
                set_id=tire_set.id,
                round_id=int(round_id) if round_id else None,
                track_id=track_id,
                event_type=event_type,
                date=session_date,
                lap_stop=lap_stop,
                notes=request.form.get('pitstop_notes', '').strip() or None,
            )
            db.session.add(pit_stop_obj)
            db.session.flush()

        created = 0
        alerts = []
        pitstop_changes = []

        for pos, tire in positions_tires:
            if not tire:
                continue

            is_swap = has_pitstop and request.form.get(f'{pos.lower()}_swap') == '1'

            twi_int_raw = request.form.get(f'{pos.lower()}_twi_int', '').strip()
            twi_ci_raw  = request.form.get(f'{pos.lower()}_twi_ci',  '').strip()
            twi_co_raw  = request.form.get(f'{pos.lower()}_twi_co',  '').strip()
            twi_ext_raw = request.form.get(f'{pos.lower()}_twi_ext', '').strip()
            twi_data = calc_twi(twi_int_raw, twi_ci_raw, twi_co_raw, twi_ext_raw,
                                tire.twi_initial_int, tire.twi_initial_ci,
                                tire.twi_initial_co, tire.twi_initial_ext)

            twi_int = twi_ci = twi_co = twi_ext = twi_avg = None
            pct_int = pct_ci = pct_co = pct_ext = pct_avg = None
            if twi_data:
                twi_int, twi_ci, twi_co, twi_ext = twi_data['twi_int'], twi_data['twi_ci'], twi_data['twi_co'], twi_data['twi_ext']
                twi_avg = twi_data['twi_avg']
                pct_int, pct_ci, pct_co, pct_ext, pct_avg = twi_data['pct_int'], twi_data['pct_ci'], twi_data['pct_co'], twi_data['pct_ext'], twi_data['pct_avg']

            if is_swap:
                laps_for_session = lap_stop
                km_for_session = km_stint
                notes_for_session = f'Pit stop — volta {lap_stop}'
            elif tire.id in pit_swap_info:
                # Tire entered mid-race; record only its stint laps
                pit_lap = pit_swap_info[tire.id]
                laps_for_session = max(0, laps - pit_lap)
                km_for_session = round(laps_for_session * km_per_lap, 3) if km_per_lap else (round(km_session * laps_for_session / laps, 3) if laps else 0)
                notes_for_session = request.form.get(f'{pos.lower()}_notes', '').strip() or None
            else:
                laps_for_session = laps
                km_for_session = km_session
                notes_for_session = request.form.get(f'{pos.lower()}_notes', '').strip() or None

            km_cumulative = (tire.total_km or 0) + km_for_session

            session = Session(
                team_id=team_id,
                tire_id=tire.id,
                set_id=tire_set.id,
                round_id=int(round_id) if round_id else None,
                track_id=track_id,
                driver_id=tire_set.driver_id,
                event_type=event_type,
                position=pos,
                date=session_date,
                laps=laps_for_session,
                km_session=km_for_session,
                km_cumulative=km_cumulative,
                twi_int=twi_int, twi_ci=twi_ci, twi_co=twi_co, twi_ext=twi_ext,
                twi_avg=twi_avg,
                twi_pct_int=pct_int, twi_pct_ci=pct_ci, twi_pct_co=pct_co, twi_pct_ext=pct_ext,
                twi_pct_avg=pct_avg,
                notes=notes_for_session,
            )
            db.session.add(session)

            tire.total_km = km_cumulative
            tire.total_laps = (tire.total_laps or 0) + laps_for_session
            if twi_data:
                tire.update_current_twi(twi_int, twi_ci, twi_co, twi_ext)

            created += 1
            if twi_data and pct_avg is not None and pct_avg < 20:
                alerts.append(f'{tire.code} ({pos}) CRÍTICO: {pct_avg:.0f}%')
            elif twi_data and pct_avg is not None and pct_avg < 40:
                alerts.append(f'{tire.code} ({pos}) alerta: {pct_avg:.0f}%')

            if is_swap:
                new_tire_id = request.form.get(f'{pos.lower()}_new_tire_id')
                tire_in = Tire.query.filter_by(id=int(new_tire_id), team_id=team_id).first() if new_tire_id else None
                if tire_in:
                    # TWI of incoming tire at pit entry (optional)
                    in_twi_data = calc_twi(
                        request.form.get(f'{pos.lower()}_in_twi_int', '').strip(),
                        request.form.get(f'{pos.lower()}_in_twi_ci',  '').strip(),
                        request.form.get(f'{pos.lower()}_in_twi_co',  '').strip(),
                        request.form.get(f'{pos.lower()}_in_twi_ext', '').strip(),
                        tire_in.twi_initial_int, tire_in.twi_initial_ci,
                        tire_in.twi_initial_co, tire_in.twi_initial_ext,
                    )
                    tire.status = 'available'
                    setattr(tire_set, pos_field_map[pos], tire_in.id)
                    tire_in.status = 'mounted'
                    if in_twi_data:
                        tire_in.update_current_twi(in_twi_data['twi_int'], in_twi_data['twi_ci'],
                                                   in_twi_data['twi_co'], in_twi_data['twi_ext'])
                    db.session.add(PitStopChange(
                        pit_stop_id=pit_stop_obj.id,
                        position=pos,
                        tire_out_id=tire.id,
                        tire_in_id=tire_in.id,
                        twi_int=twi_int, twi_ci=twi_ci, twi_co=twi_co, twi_ext=twi_ext,
                    ))
                    pitstop_changes.append(f'{pos}: {tire.code} → {tire_in.code}')

        db.session.commit()

        if has_pitstop and pitstop_changes:
            msg = f'Sessão + Pit stop (v.{lap_stop}) · {" | ".join(pitstop_changes)}'
            flash(msg + (f' ⚠️ {" | ".join(alerts)}' if alerts else ''), 'warning' if alerts else 'success')
        elif alerts:
            flash(f'Sessão do set "{tire_set.name}" registrada! ⚠️ {" | ".join(alerts)}', 'warning')
        else:
            flash(f'Sessão do set "{tire_set.name}" registrada para {created} pneu(s)! ✓', 'success')

        return redirect(url_for('sets.index'))

    return render_template('sets/session_new.html',
                           tire_set=tire_set,
                           positions_tires=positions_tires,
                           available_tires=available_tires,
                           available_tires_json=available_tires_json,
                           tire_initials_json=tire_initials_json,
                           pit_swap_info=pit_swap_info,
                           tracks=tracks,
                           rounds=rounds)



