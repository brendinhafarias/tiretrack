from flask import Blueprint

sets_bp = Blueprint('sets', __name__, url_prefix='/sets')

from app.blueprints.sets import routes  # noqa
