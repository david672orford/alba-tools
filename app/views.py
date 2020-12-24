from flask import request, render_template, redirect
from . import app
from .alba import Territory

@app.route("/")
def view_index():
	return render_template("index.html")

@app.route("/print")
def view_print():
	url = request.args.get('url')
	try:
		territory = Territory(url)
		territory.per_page = 30
	except Exception:
		return redirect(".")
	return render_template("print.html", territory=territory)

@app.route("/research")
def view_research():
	url = request.args.get('url')
	try:
		territory = Territory(url, load_all=True)
	except Exception:
		return redirect(".")
	return render_template("research.html", territory=territory)

