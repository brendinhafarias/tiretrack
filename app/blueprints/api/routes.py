from flask import jsonify, request
from flask_login import login_required, current_user
from app.blueprints.api import api_bp
from app.models import Tire, Track, Session, TireSet, Driver
from app.extensions import db


@api_bp.route('/tire/<int:tire_id>/preview')
@login_required
def tire_preview(tire_id):
    tire = Tire.query.filter_by(id=tire_id, team_id=current_user.team_id).first()
    if not tire:
        return jsonify({'error': 'Not found'}), 404

    last_sessions = Session.query.filter_by(tire_id=tire_id).order_by(
        Session.date.desc(), Session.created_at.desc()
    ).limit(5).all()

    active_set = tire.get_active_set()
    position = tire.get_position_in_set(active_set) if active_set else None

    from sqlalchemy import func as sqlfunc
    tracks_raw = db.session.query(
        Track.name,
        sqlfunc.sum(Session.km_session),
        sqlfunc.count(Session.id)
    ).join(Session, Session.track_id == Track.id).filter(
        Session.tire_id == tire_id
    ).group_by(Track.name).order_by(sqlfunc.sum(Session.km_session).desc()).all()

    tracks = [{'name': r[0], 'km': round(float(r[1]), 1), 'sessions': r[2]} for r in tracks_raw]

    positions_raw = db.session.query(Session.position).filter(
        Session.tire_id == tire_id, Session.position.isnot(None)
    ).distinct().all()
    positions = [p[0] for p in positions_raw if p[0]]

    return jsonify({
        'id': tire.id,
        'code': tire.code,
        'tire_type': tire.tire_type,
        'compound': tire.compound,
        'status': tire.status,
        'total_km': round(tire.total_km or 0, 1),
        'total_laps': tire.total_laps or 0,
        'current_twi_avg': round(tire.current_twi_avg or 0, 2),
        'current_twi_pct': round(tire.current_twi_pct or 100, 1),
        'twi_int': tire.current_twi_int,
        'twi_ci': tire.current_twi_ci,
        'twi_co': tire.current_twi_co,
        'twi_ext': tire.current_twi_ext,
        'twi_initial_int': tire.twi_initial_int,
        'twi_initial_ci': tire.twi_initial_ci,
        'twi_initial_co': tire.twi_initial_co,
        'twi_initial_ext': tire.twi_initial_ext,
        'active_set': active_set.name if active_set else None,
        'position': position,
        'driver': tire.driver.name if tire.driver else None,
        'tracks': tracks,
        'positions': positions,
        'photos': [
            {'url': '/' + p.path.replace('\\', '/'), 'thumb': '/' + p.thumb_path.replace('\\', '/') if p.thumb_path else '/' + p.path.replace('\\', '/')}
            for p in tire.photos.all()
        ],
        'sessions': [
            {
                'date': s.date.strftime('%d/%m/%Y'),
                'track': s.track.name if s.track else 'desconhecida',
                'event_type': s.event_type_label,
                'position': s.position or '-',
                'laps': s.laps,
                'km': round(s.km_session, 1),
                'twi_pct': round(s.twi_pct_avg or 100, 0)
            }
            for s in last_sessions
        ]
    })


@api_bp.route('/track/<int:track_id>/km')
@login_required
def track_km(track_id):
    track = Track.query.filter(
        (Track.id == track_id) &
        ((Track.is_global == True) | (Track.team_id == current_user.team_id))
    ).first()
    if not track:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'km_per_lap': track.km_per_lap})


@api_bp.route('/tires')
@login_required
def tires_list():
    driver_id = request.args.get('driver_id', type=int)
    status = request.args.get('status', 'available')
    team_id = current_user.team_id
    q = Tire.query.filter_by(team_id=team_id)
    if driver_id:
        q = q.filter_by(driver_id=driver_id)
    if status:
        q = q.filter_by(status=status)
    tires = q.order_by(Tire.code).all()
    return jsonify([{
        'id': t.id,
        'code': t.code,
        'tire_type': t.tire_type,
        'compound': t.compound,
        'status': t.status,
        'total_km': t.total_km,
        'current_twi_pct': t.current_twi_pct,
        'driver': t.driver.name if t.driver else None,
    } for t in tires])


@api_bp.route('/set/<int:set_id>/session-form')
@login_required
def set_session_form(set_id):
    tire_set = TireSet.query.filter_by(id=set_id, team_id=current_user.team_id).first()
    if not tire_set:
        return jsonify({'error': 'Not found'}), 404
    result = []
    for pos, tire in [('DE', tire_set.tire_de), ('DD', tire_set.tire_dd),
                      ('TE', tire_set.tire_te), ('TD', tire_set.tire_td)]:
        if tire:
            result.append({
                'position': pos,
                'tire_id': tire.id,
                'code': tire.code,
                'twi_initial_int': tire.twi_initial_int,
                'twi_initial_ci': tire.twi_initial_ci,
                'twi_initial_co': tire.twi_initial_co,
                'twi_initial_ext': tire.twi_initial_ext,
                'current_twi_int': tire.current_twi_int,
                'current_twi_ci': tire.current_twi_ci,
                'current_twi_co': tire.current_twi_co,
                'current_twi_ext': tire.current_twi_ext,
            })
    return jsonify({'set': tire_set.name, 'tires': result})
