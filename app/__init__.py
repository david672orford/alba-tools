from flask import Flask
from urllib.parse import quote_plus
from markupsafe import Markup
import re

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    )
app.config.from_pyfile('config.py')

@app.template_filter('urlencode')
def urlencode_filter(s):
	return Markup(quote_plus(s.encode('utf-8')))

@app.template_filter('weirdencode')
def weirdencode_filter(s):
	s = s.lower()
	s = re.sub(r"[^ 0-9a-z]", "", s)
	s = s.replace(" ", "-")
	return Markup(s)

@app.template_filter('phoneencode')
def phoneencode_filter(s):
	s = re.sub(r"[^\d]", "", s)
	if len(s) == 10:
		return Markup("%s-%s-%s" % (s[:3], s[3:6], s[6:]))
	return ""

from . import views
