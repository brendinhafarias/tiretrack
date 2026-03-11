from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.blueprints.sets import sets_bp
from app.models import TireSet, Tire, Driver
from app.extensions import db
from app.utils import require_write


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

    positions_tires = [
        ('DE', tire_set.tire_de),
        ('DD', tire_set.tire_dd),
        ('TE', tire_set.tire_te),
        ('TD', tire_set.tire_td),
    ]

    if request.method == 'POST':
        track_id = int(request.form.get('track_id'))
        round_id = request.form.get('round_id') or None
        event_type = request.form.get('event_type', 'practice')
        session_date = date_cls.fromisoformat(request.form.get('date', date_cls.today().isoformat()))
        laps = int(request.form.get('laps'))
        km_manual = request.form.get('km_manual')

        track = Track.query.get(track_id)
        if track and track.km_per_lap:
            km_session = round(laps * track.km_per_lap, 3)
        else:
            km_session = float(km_manual or 0)

        created = 0
        alerts = []

        for pos, tire in positions_tires:
            if not tire:
                continue

            twi_int = request.form.get(f'{pos.lower()}_twi_int')
            twi_ci  = request.form.get(f'{pos.lower()}_twi_ci')
            twi_co  = request.form.get(f'{pos.lower()}_twi_co')
            twi_ext = request.form.get(f'{pos.lower()}_twi_ext')

            # Skip if fields empty (tire not measured)
            if not all([twi_int, twi_ci, twi_co, twi_ext]):
                continue

            twi_int = float(twi_int)
            twi_ci  = float(twi_ci)
            twi_co  = float(twi_co)
            twi_ext = float(twi_ext)
            twi_avg = round((twi_int + twi_ci + twi_co + twi_ext) / 4, 2)

            pct_int = round((twi_int / tire.twi_initial_int) * 100, 1) if tire.twi_initial_int else 100
            pct_ci  = round((twi_ci  / tire.twi_initial_ci)  * 100, 1) if tire.twi_initial_ci  else 100
            pct_co  = round((twi_co  / tire.twi_initial_co)  * 100, 1) if tire.twi_initial_co  else 100
            pct_ext = round((twi_ext / tire.twi_initial_ext) * 100, 1) if tire.twi_initial_ext else 100
            pct_avg = round((pct_int + pct_ci + pct_co + pct_ext) / 4, 1)

            km_cumulative = (tire.total_km or 0) + km_session
            notes = request.form.get(f'{pos.lower()}_notes', '').strip() or None

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
                laps=laps,
                km_session=km_session,
                km_cumulative=km_cumulative,
                twi_int=twi_int, twi_ci=twi_ci, twi_co=twi_co, twi_ext=twi_ext,
                twi_avg=twi_avg,
                twi_pct_int=pct_int, twi_pct_ci=pct_ci, twi_pct_co=pct_co, twi_pct_ext=pct_ext,
                twi_pct_avg=pct_avg,
                notes=notes,
            )
            db.session.add(session)

            tire.total_km = km_cumulative
            tire.total_laps = (tire.total_laps or 0) + laps
            tire.update_current_twi(twi_int, twi_ci, twi_co, twi_ext)

            created += 1
            if pct_avg < 20:
                alerts.append(f'{tire.code} ({pos}) CRÍTICO: {pct_avg:.0f}%')
            elif pct_avg < 40:
                alerts.append(f'{tire.code} ({pos}) alerta: {pct_avg:.0f}%')

        db.session.commit()

        if alerts:
            flash(f'Sessão do set "{tire_set.name}" registrada! ⚠️ {" | ".join(alerts)}', 'warning')
        else:
            flash(f'Sessão do set "{tire_set.name}" registrada para {created} pneu(s)! ✓', 'success')

        return redirect(url_for('sets.index'))

    return render_template('sets/session_new.html',
                           tire_set=tire_set,
                           positions_tires=positions_tires,
                           tracks=tracks,
                           rounds=rounds)
