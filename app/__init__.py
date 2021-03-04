from flask import Flask
from urllib.parse import quote_plus
from markupsafe import Markup

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    )
app.config.from_pyfile('config.py')


@app.template_filter('urlencode')
def urlencode_filter(s):
	return Markup(quote_plus(s.encode('utf-8')))

from . import views
