from flask import render_template, request
from flask_login import login_required, current_user
from app.blueprints.charts import charts_bp
from app.models import Tire, Session, Driver
from app.extensions import db


@charts_bp.route('/')
@login_required
def index():
    team_id = current_user.team_id

    # Filters
    driver_filter = request.args.get('driver_id', type=int)
    status_filter = request.args.getlist('status') or ['available', 'mounted', 'blocked']

    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).order_by(Driver.name).all()

    q = Tire.query.filter(
        Tire.team_id == team_id,
        Tire.status.in_(status_filter)
    )
    if driver_filter:
        q = q.filter(Tire.driver_id == driver_filter)

    tires = q.order_by(Tire.code).all()

    # Build chart data for each tire
    tire_charts = []
    for t in tires:
        # Last session with TWI data
        last_session = Session.query.filter(
            Session.tire_id == t.id,
            Session.twi_ext.isnot(None)
        ).order_by(Session.date.desc(), Session.created_at.desc()).first()

        pct = t.current_twi_pct or 100
        if pct >= 70:
            color = '#22c55e'
        elif pct >= 40:
            color = '#eab308'
        elif pct >= 20:
            color = '#f97316'
        else:
            color = '#ef4444'

        tire_charts.append({
            'id': t.id,
            'code': t.code,
            'driver': t.driver.name if t.driver else '—',
            'status': t.status,
            'pct': round(pct, 1),
            'color': color,
            'initial': [t.twi_initial_ext, t.twi_initial_co, t.twi_initial_ci, t.twi_initial_int],
            'last': [last_session.twi_ext, last_session.twi_co, last_session.twi_ci, last_session.twi_int] if last_session else None,
            'last_label': last_session.date.strftime('%d/%m/%y') if last_session else None,
        })

    return render_template(
        'charts/index.html',
        tire_charts=tire_charts,
        drivers=drivers,
        driver_filter=driver_filter,
        status_filter=status_filter,
    )
