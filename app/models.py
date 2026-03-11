from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    logo_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='team', lazy='dynamic', foreign_keys='User.team_id')
    drivers = db.relationship('Driver', backref='team', lazy='dynamic')
    tires = db.relationship('Tire', backref='team', lazy='dynamic')
    tire_sets = db.relationship('TireSet', backref='team', lazy='dynamic')
    rounds = db.relationship('Round', backref='team', lazy='dynamic')

    def __repr__(self):
        return f'<Team {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    ROLES = ['superadmin', 'team_admin', 'team_user', 'viewer']

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='team_user')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    observations = db.relationship('Observation', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    @property
    def is_team_admin(self):
        return self.role in ('superadmin', 'team_admin')

    @property
    def can_write(self):
        return self.role in ('superadmin', 'team_admin', 'team_user')

    def __repr__(self):
        return f'<User {self.username}>'


class Driver(db.Model):
    __tablename__ = 'drivers'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    number = db.Column(db.String(10))
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tires = db.relationship('Tire', backref='driver', lazy='dynamic')
    tire_sets = db.relationship('TireSet', backref='driver', lazy='dynamic')
    rounds = db.relationship('Round', backref='driver', lazy='dynamic')

    def __repr__(self):
        return f'<Driver {self.name}>'


class Track(db.Model):
    __tablename__ = 'tracks'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    km_per_lap = db.Column(db.Float)
    location = db.Column(db.String(100))
    is_global = db.Column(db.Boolean, default=False, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)

    sessions = db.relationship('Session', backref='track', lazy='dynamic')
    rounds = db.relationship('Round', backref='track', lazy='dynamic')

    def __repr__(self):
        return f'<Track {self.name}>'


class Round(db.Model):
    __tablename__ = 'rounds'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('tracks.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='open', nullable=False)  # open, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('Session', backref='round', lazy='dynamic')

    def __repr__(self):
        return f'<Round {self.name}>'


class Tire(db.Model):
    __tablename__ = 'tires'

    STATUSES = ['available', 'mounted', 'blocked', 'trash']
    TYPES = ['slick', 'wet']
    COMPOUNDS = ['soft', 'medium', 'hard', 'intermediate', 'custom']

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=True)
    code = db.Column(db.String(50), nullable=False)
    barcode = db.Column(db.String(100))
    tire_type = db.Column(db.String(10), nullable=False, default='slick')  # slick, wet
    compound = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), nullable=False, default='available')

    # Initial readings (reference base for % calculation)
    km_initial = db.Column(db.Float, default=0.0)
    twi_initial_int = db.Column(db.Float, nullable=False)
    twi_initial_ci = db.Column(db.Float, nullable=False)
    twi_initial_co = db.Column(db.Float, nullable=False)
    twi_initial_ext = db.Column(db.Float, nullable=False)

    # Current readings (updated on each session save)
    total_km = db.Column(db.Float, default=0.0)
    total_laps = db.Column(db.Integer, default=0)
    current_twi_int = db.Column(db.Float)
    current_twi_ci = db.Column(db.Float)
    current_twi_co = db.Column(db.Float)
    current_twi_ext = db.Column(db.Float)
    current_twi_avg = db.Column(db.Float)
    current_twi_pct = db.Column(db.Float)  # average % remaining

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('Session', backref='tire', lazy='dynamic', order_by='Session.date.desc()')
    observations = db.relationship('Observation', backref='tire', lazy='dynamic', order_by='Observation.created_at.desc()')
    photos = db.relationship('TirePhoto', backref='tire', lazy='dynamic', order_by='TirePhoto.created_at.asc()')
    round = db.relationship('Round', foreign_keys=[round_id], backref='registered_tires')

    @property
    def twi_pct_int(self):
        if self.current_twi_int and self.twi_initial_int:
            return round((self.current_twi_int / self.twi_initial_int) * 100, 1)
        return 100.0

    @property
    def twi_pct_ci(self):
        if self.current_twi_ci and self.twi_initial_ci:
            return round((self.current_twi_ci / self.twi_initial_ci) * 100, 1)
        return 100.0

    @property
    def twi_pct_co(self):
        if self.current_twi_co and self.twi_initial_co:
            return round((self.current_twi_co / self.twi_initial_co) * 100, 1)
        return 100.0

    @property
    def twi_pct_ext(self):
        if self.current_twi_ext and self.twi_initial_ext:
            return round((self.current_twi_ext / self.twi_initial_ext) * 100, 1)
        return 100.0

    @property
    def status_color(self):
        colors = {
            'available': 'green',
            'mounted': 'blue',
            'blocked': 'red',
            'trash': 'gray'
        }
        return colors.get(self.status, 'gray')

    @property
    def twi_color(self):
        pct = self.current_twi_pct or 100.0
        if pct >= 70:
            return 'green'
        elif pct >= 40:
            return 'yellow'
        elif pct >= 20:
            return 'orange'
        return 'red'

    def update_current_twi(self, twi_int, twi_ci, twi_co, twi_ext):
        self.current_twi_int = twi_int
        self.current_twi_ci = twi_ci
        self.current_twi_co = twi_co
        self.current_twi_ext = twi_ext
        vals = [v for v in [twi_int, twi_ci, twi_co, twi_ext] if v is not None]
        self.current_twi_avg = round(sum(vals) / len(vals), 2) if vals else None
        pct_int = (twi_int / self.twi_initial_int) * 100 if twi_int is not None and self.twi_initial_int else None
        pct_ci  = (twi_ci  / self.twi_initial_ci)  * 100 if twi_ci  is not None and self.twi_initial_ci  else None
        pct_co  = (twi_co  / self.twi_initial_co)  * 100 if twi_co  is not None and self.twi_initial_co  else None
        pct_ext = (twi_ext / self.twi_initial_ext) * 100 if twi_ext is not None and self.twi_initial_ext else None
        pcts = [p for p in [pct_int, pct_ci, pct_co, pct_ext] if p is not None]
        self.current_twi_pct = round(sum(pcts) / len(pcts), 1) if pcts else None

    def get_active_set(self):
        return TireSet.query.filter(
            db.or_(
                TireSet.tire_de_id == self.id,
                TireSet.tire_dd_id == self.id,
                TireSet.tire_te_id == self.id,
                TireSet.tire_td_id == self.id,
            ),
            TireSet.status == 'active'
        ).first()

    def get_position_in_set(self, tire_set):
        if tire_set.tire_de_id == self.id:
            return 'DE'
        if tire_set.tire_dd_id == self.id:
            return 'DD'
        if tire_set.tire_te_id == self.id:
            return 'TE'
        if tire_set.tire_td_id == self.id:
            return 'TD'
        return None

    def get_tracks_used(self):
        track_ids = db.session.query(Session.track_id).filter_by(tire_id=self.id).distinct().all()
        tracks = []
        for (tid,) in track_ids:
            t = Track.query.get(tid)
            if t:
                tracks.append(t)
        return tracks

    def __repr__(self):
        return f'<Tire {self.code}>'


class TireSet(db.Model):
    __tablename__ = 'tire_sets'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')  # active, dismounted

    tire_de_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=True)
    tire_dd_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=True)
    tire_te_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=True)
    tire_td_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dismounted_at = db.Column(db.DateTime)

    tire_de = db.relationship('Tire', foreign_keys=[tire_de_id])
    tire_dd = db.relationship('Tire', foreign_keys=[tire_dd_id])
    tire_te = db.relationship('Tire', foreign_keys=[tire_te_id])
    tire_td = db.relationship('Tire', foreign_keys=[tire_td_id])

    @property
    def tires(self):
        return [t for t in [self.tire_de, self.tire_dd, self.tire_te, self.tire_td] if t]

    @property
    def tires_with_position(self):
        result = []
        for pos, tire in [('DE', self.tire_de), ('DD', self.tire_dd), ('TE', self.tire_te), ('TD', self.tire_td)]:
            result.append({'position': pos, 'tire': tire})
        return result

    def __repr__(self):
        return f'<TireSet {self.name}>'


class Session(db.Model):
    __tablename__ = 'sessions'

    EVENT_TYPES = ['fp1', 'fp2', 'extra', 'q1', 'q2', 'q3', 'warmup', 'sprint', 'race', 'test']

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    tire_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=False)
    set_id = db.Column(db.Integer, db.ForeignKey('tire_sets.id'), nullable=True)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=True)
    track_id = db.Column(db.Integer, db.ForeignKey('tracks.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=True)

    event_type = db.Column(db.String(20), nullable=False)
    position = db.Column(db.String(5))  # DE, DD, TE, TD
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    laps = db.Column(db.Integer, nullable=False)
    km_session = db.Column(db.Float, nullable=False)
    km_cumulative = db.Column(db.Float, nullable=False)

    # TWI readings in mm (nullable — session may be recorded without TWI measurement)
    twi_int = db.Column(db.Float, nullable=True)
    twi_ci = db.Column(db.Float, nullable=True)
    twi_co = db.Column(db.Float, nullable=True)
    twi_ext = db.Column(db.Float, nullable=True)
    twi_avg = db.Column(db.Float, nullable=True)

    # TWI % remaining (calculated from initial values)
    twi_pct_int = db.Column(db.Float)
    twi_pct_ci = db.Column(db.Float)
    twi_pct_co = db.Column(db.Float)
    twi_pct_ext = db.Column(db.Float)
    twi_pct_avg = db.Column(db.Float)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tire_set = db.relationship('TireSet', backref='sessions', foreign_keys=[set_id])
    driver = db.relationship('Driver', foreign_keys=[driver_id])

    @property
    def event_type_label(self):
        labels = {
            'fp1': 'Treino Livre 1',
            'fp2': 'Treino Livre 2',
            'extra': 'Treino Extra',
            'q1': 'Classificação Q1',
            'q2': 'Classificação Q2',
            'q3': 'Classificação Q3',
            'warmup': 'Warm-up',
            'sprint': 'Corrida Sprint',
            'race': 'Corrida Principal',
            'test': 'Teste',
            # legacy
            'practice': 'Treino',
            'qualifying': 'Classificação',
        }
        return labels.get(self.event_type, self.event_type)

    def __repr__(self):
        return f'<Session tire={self.tire_id} date={self.date}>'


class Observation(db.Model):
    __tablename__ = 'observations'

    ACTIONS = ['ok', 'monitor', 'review', 'block', 'release', 'discard']

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    tire_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=True)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    text = db.Column(db.Text, nullable=False)
    action = db.Column(db.String(20), nullable=False, default='ok')
    photo_path = db.Column(db.String(255))
    photo_thumb_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('Session', backref='observations')

    @property
    def action_label(self):
        labels = {
            'ok': 'OK',
            'monitor': 'Monitorar',
            'review': 'Revisar',
            'block': 'Bloquear',
            'release': 'Liberar',
            'discard': 'Descartar'
        }
        return labels.get(self.action, self.action)

    @property
    def action_color(self):
        colors = {
            'ok': 'green',
            'monitor': 'yellow',
            'review': 'blue',
            'block': 'red',
            'release': 'green',
            'discard': 'gray'
        }
        return colors.get(self.action, 'gray')

    def __repr__(self):
        return f'<Observation tire={self.tire_id} action={self.action}>'


class PitStop(db.Model):
    __tablename__ = 'pit_stops'

    id         = db.Column(db.Integer, primary_key=True)
    team_id    = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    set_id     = db.Column(db.Integer, db.ForeignKey('tire_sets.id'), nullable=False)
    round_id   = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=True)
    track_id   = db.Column(db.Integer, db.ForeignKey('tracks.id'), nullable=True)
    event_type = db.Column(db.String(20), default='race')
    date       = db.Column(db.Date, nullable=False)
    lap_stop   = db.Column(db.Integer, nullable=False)
    notes      = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    changes = db.relationship('PitStopChange', backref='pit_stop', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PitStop set={self.set_id} lap={self.lap_stop}>'


class PitStopChange(db.Model):
    __tablename__ = 'pit_stop_changes'

    id          = db.Column(db.Integer, primary_key=True)
    pit_stop_id = db.Column(db.Integer, db.ForeignKey('pit_stops.id'), nullable=False)
    position    = db.Column(db.String(2), nullable=False)
    tire_out_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=False)
    tire_in_id  = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=False)
    twi_int     = db.Column(db.Float, nullable=True)
    twi_ci      = db.Column(db.Float, nullable=True)
    twi_co      = db.Column(db.Float, nullable=True)
    twi_ext     = db.Column(db.Float, nullable=True)

    tire_out = db.relationship('Tire', foreign_keys=[tire_out_id])
    tire_in  = db.relationship('Tire', foreign_keys=[tire_in_id])

    def __repr__(self):
        return f'<PitStopChange pos={self.position} out={self.tire_out_id} in={self.tire_in_id}>'


class TirePhoto(db.Model):
    __tablename__ = 'tire_photos'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    tire_id = db.Column(db.Integer, db.ForeignKey('tires.id'), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    thumb_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TirePhoto tire={self.tire_id}>'
