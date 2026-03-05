from flask import Blueprint

rounds_bp = Blueprint('rounds', __name__, url_prefix='/rounds')

from app.blueprints.rounds import routes  # noqa
