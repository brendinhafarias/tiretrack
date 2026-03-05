"""
seed.py — Populates the TireTrack Pro database with initial demo data.

Usage:
    python seed.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import User, Team, Driver, Track, Tire, TireSet, Round, Session
from datetime import date


TRACKS = [
    ('Interlagos', 4.309, 'São Paulo-SP'),
    ('Velocitta', 3.493, 'Mogi Guaçu-SP'),
    ('Circuito dos Cristais', 3.477, 'Curvelo-MG'),
    ('Velopark', 3.013, 'Nova Santa Rita-RS'),
    ('Autódromo Nelson Piquet', 5.476, 'Brasília-DF'),
    ('Autódromo Ayrton Senna', 3.835, 'Goiânia-GO'),
    ('Autódromo Zilmar Beux', 3.115, 'Cascavel-PR'),
    ('Autódromo de Cuiabá', 3.408, 'Cuiabá-MT'),
    ('Autódromo de Chapecó', 3.762, 'Chapecó-SC'),
]


def seed():
    app = create_app('development')

    with app.app_context():
        db.create_all()

        # ---- Global tracks ----
        if not Track.query.filter_by(is_global=True).first():
            print('Criando pistas globais...')
            for name, km, location in TRACKS:
                track = Track(name=name, km_per_lap=km, location=location, is_global=True)
                db.session.add(track)
            db.session.flush()

        # ---- Superadmin ----
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print('Criando superadmin...')
            admin = User(
                username='admin',
                email='admin@tiretrackpro.com',
                role='superadmin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.flush()

        # ---- Demo Team ----
        demo_team = Team.query.filter_by(slug='demo').first()
        if not demo_team:
            print('Criando equipe demo...')
            demo_team = Team(name='Equipe Demo', slug='demo', is_active=True)
            db.session.add(demo_team)
            db.session.flush()

        # ---- Team admin ----
        demo_admin = User.query.filter_by(username='demo_admin').first()
        if not demo_admin:
            print('Criando demo_admin...')
            demo_admin = User(
                username='demo_admin',
                email='demo_admin@tiretrackpro.com',
                role='team_admin',
                team_id=demo_team.id,
                is_active=True
            )
            demo_admin.set_password('demo123')
            db.session.add(demo_admin)
            db.session.flush()

        # ---- Team user ----
        demo_user = User.query.filter_by(username='demo_user').first()
        if not demo_user:
            print('Criando demo_user...')
            demo_user = User(
                username='demo_user',
                email='demo_user@tiretrackpro.com',
                role='team_user',
                team_id=demo_team.id,
                is_active=True
            )
            demo_user.set_password('user123')
            db.session.add(demo_user)
            db.session.flush()

        # ---- Demo Driver ----
        driver = Driver.query.filter_by(team_id=demo_team.id).first()
        if not driver:
            print('Criando piloto demo...')
            driver = Driver(
                team_id=demo_team.id,
                name='Piloto Demo',
                number='77',
                category='Stock Car',
                is_active=True
            )
            db.session.add(driver)
            db.session.flush()

        # ---- Demo Tires ----
        if not Tire.query.filter_by(team_id=demo_team.id).first():
            print('Criando pneus de demonstração...')
            tire_specs = [
                ('P-001', 'slick', 'soft',   8.0, 7.8, 7.9, 8.1),
                ('P-002', 'slick', 'soft',   8.0, 8.0, 8.0, 8.0),
                ('P-003', 'slick', 'medium', 7.5, 7.5, 7.5, 7.5),
                ('P-004', 'slick', 'medium', 7.5, 7.5, 7.5, 7.5),
                ('P-005', 'slick', 'hard',   8.5, 8.5, 8.5, 8.5),
                ('P-006', 'slick', 'hard',   8.5, 8.5, 8.5, 8.5),
                ('P-007', 'wet',   'intermediate', 9.0, 9.0, 9.0, 9.0),
                ('P-008', 'wet',   'intermediate', 9.0, 9.0, 9.0, 9.0),
            ]
            tires = []
            for code, ttype, compound, int_v, ci_v, co_v, ext_v in tire_specs:
                t = Tire(
                    team_id=demo_team.id,
                    driver_id=driver.id,
                    code=code,
                    tire_type=ttype,
                    compound=compound,
                    status='available',
                    km_initial=0,
                    total_km=0,
                    total_laps=0,
                    twi_initial_int=int_v,
                    twi_initial_ci=ci_v,
                    twi_initial_co=co_v,
                    twi_initial_ext=ext_v,
                    current_twi_int=int_v,
                    current_twi_ci=ci_v,
                    current_twi_co=co_v,
                    current_twi_ext=ext_v,
                    current_twi_avg=round((int_v + ci_v + co_v + ext_v) / 4, 2),
                    current_twi_pct=100.0,
                )
                db.session.add(t)
                tires.append(t)
            db.session.flush()

            # ---- Demo Sessions for P-001 and P-002 (to show history) ----
            track = Track.query.filter_by(name='Interlagos').first()
            track2 = Track.query.filter_by(name='Velocitta').first()

            if track and len(tires) >= 2:
                print('Criando sessões de demonstração...')
                t1 = tires[0]  # P-001
                sessions_data = [
                    (date(2026, 1, 15), track.id, 'practice', 'DE', 20, 7.2, 7.0, 7.1, 7.3),
                    (date(2026, 1, 15), track.id, 'qualifying', 'DE', 5, 6.8, 6.6, 6.7, 6.9),
                    (date(2026, 1, 16), track.id, 'race', 'DE', 40, 5.5, 5.2, 5.4, 5.7),
                ]
                km_cum = t1.km_initial
                for sess_date, track_id, etype, pos, laps, twi_i, twi_ci, twi_co, twi_e in sessions_data:
                    track_obj = Track.query.get(track_id)
                    km_sess = round(laps * track_obj.km_per_lap, 3)
                    km_cum += km_sess
                    twi_avg = round((twi_i + twi_ci + twi_co + twi_e) / 4, 2)
                    pct_i = round((twi_i / t1.twi_initial_int) * 100, 1)
                    pct_ci = round((twi_ci / t1.twi_initial_ci) * 100, 1)
                    pct_co = round((twi_co / t1.twi_initial_co) * 100, 1)
                    pct_e = round((twi_e / t1.twi_initial_ext) * 100, 1)
                    pct_avg = round((pct_i + pct_ci + pct_co + pct_e) / 4, 1)

                    s = Session(
                        team_id=demo_team.id,
                        tire_id=t1.id,
                        track_id=track_id,
                        driver_id=driver.id,
                        event_type=etype,
                        position=pos,
                        date=sess_date,
                        laps=laps,
                        km_session=km_sess,
                        km_cumulative=km_cum,
                        twi_int=twi_i, twi_ci=twi_ci, twi_co=twi_co, twi_ext=twi_e,
                        twi_avg=twi_avg,
                        twi_pct_int=pct_i, twi_pct_ci=pct_ci, twi_pct_co=pct_co, twi_pct_ext=pct_e,
                        twi_pct_avg=pct_avg,
                    )
                    db.session.add(s)

                # Update tire P-001 current state
                t1.total_km = km_cum
                t1.total_laps = 65
                t1.current_twi_int = 5.5
                t1.current_twi_ci = 5.2
                t1.current_twi_co = 5.4
                t1.current_twi_ext = 5.7
                t1.current_twi_avg = 5.45
                t1.current_twi_pct = round((5.5/8.0 + 5.2/7.8 + 5.4/7.9 + 5.7/8.1) / 4 * 100, 1)

        db.session.commit()
        print('=' * 50)
        print('Seed concluído com sucesso!')
        print('=' * 50)
        print()
        print('Credenciais de acesso:')
        print('  Superadmin:  admin / admin123')
        print('  Team Admin:  demo_admin / demo123')
        print('  Team User:   demo_user / user123')
        print()
        print('Inicie o servidor: python run.py')
        print('Acesse: http://localhost:5000')


if __name__ == '__main__':
    seed()
