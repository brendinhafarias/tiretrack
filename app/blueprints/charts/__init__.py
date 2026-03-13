from flask import Blueprint

charts_bp = Blueprint('charts', __name__, url_prefix='/charts')

from app.blueprints.charts import routes  # noqa
