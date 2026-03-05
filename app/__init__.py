from flask import Flask
from config import config
from app.extensions import db, login_manager, migrate


def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.blueprints.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.blueprints.tires import tires_bp
    app.register_blueprint(tires_bp)

    from app.blueprints.sets import sets_bp
    app.register_blueprint(sets_bp)

    from app.blueprints.rounds import rounds_bp
    app.register_blueprint(rounds_bp)

    from app.blueprints.reports import reports_bp
    app.register_blueprint(reports_bp)

    from app.blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.blueprints.api import api_bp
    app.register_blueprint(api_bp)

    # Auto-create new tables in dev (safe — won't touch existing tables)
    with app.app_context():
        db.create_all()
        # Add missing columns to existing tables (safe for SQLite dev)
        from sqlalchemy import text, inspect as sa_inspect
        with db.engine.connect() as conn:
            insp = sa_inspect(db.engine)
            tire_cols = [c['name'] for c in insp.get_columns('tires')]
            if 'round_id' not in tire_cols:
                conn.execute(text('ALTER TABLE tires ADD COLUMN round_id INTEGER REFERENCES rounds(id)'))
                conn.commit()

    # Context processors
    @app.context_processor
    def inject_globals():
        from app.models import Driver
        from flask_login import current_user
        drivers = []
        if current_user.is_authenticated and current_user.team_id:
            drivers = Driver.query.filter_by(
                team_id=current_user.team_id, is_active=True
            ).order_by(Driver.name).all()
        return {
            'current_year': 2026,
            'nav_drivers': drivers
        }

    return app
