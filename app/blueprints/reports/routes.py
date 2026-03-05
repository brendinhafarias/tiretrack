from datetime import datetime
from flask import render_template, redirect, url_for, flash, current_app, make_response
from flask_login import login_required, current_user
from app.blueprints.reports import reports_bp
from app.models import Round, Session, Observation, Tire
from app.extensions import db
from sqlalchemy import func


def _get_round_data(round_id, team_id):
    rnd = Round.query.filter_by(id=round_id, team_id=team_id).first_or_404()
    sessions = Session.query.filter_by(round_id=round_id).order_by(Session.date, Session.created_at).all()

    # Group by tire
    tire_map = {}
    for s in sessions:
        if s.tire_id not in tire_map:
            tire_map[s.tire_id] = {'tire': s.tire, 'sessions': []}
        tire_map[s.tire_id]['sessions'].append(s)

    tires_data = []
    for tid, data in tire_map.items():
        sorted_s = sorted(data['sessions'], key=lambda x: (x.date, x.created_at))
        first = sorted_s[0]
        last = sorted_s[-1]
        total_km = sum(s.km_session for s in data['sessions'])
        total_laps = sum(s.laps for s in data['sessions'])
        observations = Observation.query.filter_by(tire_id=tid, round_id=round_id).all()
        tires_data.append({
            'tire': data['tire'],
            'sessions': sorted_s,
            'first_session': first,
            'last_session': last,
            'total_km': round(total_km, 2),
            'total_laps': total_laps,
            'observations': observations,
        })

    # Discarded tires during round
    discarded = []
    for td in tires_data:
        if td['tire'].status == 'trash':
            discard_obs = Observation.query.filter_by(
                tire_id=td['tire'].id, action='discard'
            ).order_by(Observation.created_at.desc()).first()
            discarded.append({'tire': td['tire'], 'obs': discard_obs})

    # Deduplicate events: set sessions grouped by (set_id, date, event_type); solo by tire
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

    total_km_round = round(event_km, 2)
    total_sessions = event_count

    # Build flat observations list for template
    all_obs = []
    for td in tires_data:
        for o in td['observations']:
            all_obs.append({'tire': td['tire'], 'obs': o})

    return dict(
        rnd=rnd,
        tires_data=tires_data,
        discarded=discarded,
        all_obs=all_obs,
        total_km_round=round(total_km_round, 2),
        total_sessions=total_sessions,
        total_tires=len(tires_data),
        generated_at=datetime.now().strftime('%d/%m/%Y %H:%M'),
    )


@reports_bp.route('/round/<int:round_id>/print')
@login_required
def round_print(round_id):
    data = _get_round_data(round_id, current_user.team_id)
    return render_template('reports/print.html', **data)


@reports_bp.route('/round/<int:round_id>/pdf')
@login_required
def round_pdf(round_id):
    data = _get_round_data(round_id, current_user.team_id)
    html_content = render_template('reports/print.html', **data)

    try:
        from weasyprint import HTML
        pdf = HTML(string=html_content, base_url=current_app.root_path).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        rnd_name = data['rnd'].name.replace(' ', '_')
        response.headers['Content-Disposition'] = f'attachment; filename=relatorio_{rnd_name}.pdf'
        return response
    except ImportError:
        return redirect(url_for('reports.round_print', round_id=round_id))
    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}. Use Ctrl+P para imprimir.', 'warning')
        return render_template('reports/print.html', **data)
