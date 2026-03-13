from flask import render_template, request
from flask_login import login_required, current_user
from app.blueprints.dashboard import dashboard_bp
from app.models import Tire, TireSet, Driver, Session
from app.extensions import db
from sqlalchemy import func, or_


@dashboard_bp.route('/')
@login_required
def index():
    team_id = current_user.team_id
    if current_user.is_superadmin and not team_id:
        from app.models import Team
        teams = Team.query.filter_by(is_active=True).all()
        return render_template('dashboard/superadmin.html', teams=teams)

    sort = request.args.get('sort', 'twi')  # 'twi', 'km', 'code'
    driver_id = request.args.get('driver_id', type=int)
    tire_types = request.args.getlist('tire_type')     # multi-select
    statuses = request.args.getlist('status')           # multi-select (includes 'trash')
    set_filter = request.args.get('set_filter', '')
    categories = request.args.getlist('category')       # multi-select (driver category)

    query = Tire.query.filter_by(team_id=team_id)

    if driver_id:
        query = query.filter_by(driver_id=driver_id)
    if tire_types:
        query = query.filter(Tire.tire_type.in_(tire_types))
    if statuses:
        query = query.filter(Tire.status.in_(statuses))
    else:
        # Default: hide trash
        query = query.filter(Tire.status != 'trash')
    if categories:
        driver_ids_in_cat = [
            d.id for d in Driver.query.filter_by(team_id=team_id)
                                      .filter(Driver.category.in_(categories)).all()
        ]
        query = query.filter(Tire.driver_id.in_(driver_ids_in_cat))

    # legacy compat for sort links
    status_filter = statuses[0] if len(statuses) == 1 else ''
    tire_type = tire_types[0] if len(tire_types) == 1 else ''

    if sort == 'km':
        query = query.order_by(Tire.total_km.desc())
    elif sort == 'code':
        query = query.order_by(Tire.code.asc())
    else:
        query = query.order_by(Tire.current_twi_pct.asc().nullslast())

    tires = query.all()

    # Tires whose last session has no TWI recorded
    latest_sub = db.session.query(
        func.max(Session.id).label('max_id')
    ).filter(Session.team_id == team_id).group_by(Session.tire_id).subquery()

    no_twi_tire_ids = set(
        row.tire_id for row in db.session.query(Session.tire_id).join(
            latest_sub, Session.id == latest_sub.c.max_id
        ).filter(or_(
            Session.twi_int.is_(None),
            Session.twi_ci.is_(None),
            Session.twi_co.is_(None),
            Session.twi_ext.is_(None),
        )).all()
    )

    # Build enriched data for each tire
    tire_data = []
    for tire in tires:
        active_set = tire.get_active_set()
        if set_filter == 'active' and not active_set:
            continue
        if set_filter == 'none' and active_set:
            continue

        position = tire.get_position_in_set(active_set) if active_set else None
        tracks = tire.get_tracks_used()

        tire_data.append({
            'tire': tire,
            'active_set': active_set,
            'position': position,
            'tracks': tracks,
            'last_session_no_twi': tire.id in no_twi_tire_ids,
        })

    # Counts for summary cards
    all_tires = Tire.query.filter_by(team_id=team_id).filter(Tire.status != 'trash')
    total_active = all_tires.count()
    mounted = all_tires.filter(Tire.status == 'mounted').count()
    critical = all_tires.filter(Tire.current_twi_pct < 20).count()
    blocked = all_tires.filter(Tire.status == 'blocked').count()

    drivers = Driver.query.filter_by(team_id=team_id, is_active=True).all()
    active_sets_list = TireSet.query.filter_by(team_id=team_id, status='active').order_by(TireSet.created_at.desc()).all()
    active_sets = len(active_sets_list)

    all_categories = sorted(set(
        d.category for d in Driver.query.filter_by(team_id=team_id)
                                        .filter(Driver.category.isnot(None), Driver.category != '').all()
    ))

    return render_template('dashboard/index.html',
                           tire_data=tire_data,
                           total_active=total_active,
                           mounted=mounted,
                           critical=critical,
                           blocked=blocked,
                           active_sets=active_sets,
                           active_sets_list=active_sets_list,
                           drivers=drivers,
                           sort=sort,
                           driver_id=driver_id,
                           tire_types=tire_types,
                           statuses=statuses,
                           set_filter=set_filter,
                           categories=categories,
                           all_categories=all_categories)
