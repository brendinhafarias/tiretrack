from flask import Blueprint

tires_bp = Blueprint('tires', __name__, url_prefix='/tires')

from app.blueprints.tires import routes  # noqa
