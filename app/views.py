from flask import request, render_template, redirect, flash, make_response
import csv
from io import StringIO
import re
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
	except Exception as e:
		#raise
		flash("Exception: %s" % e)
		return redirect(".")
	return render_template("print.html", territory=territory)

@app.route("/research")
def view_research():
	url = request.args.get('url')
	try:
		territory = Territory(url, load_all=True)
	except Exception as e:
		flash("Exception: %s" % e)
		return redirect(".")
	return render_template("research.html", territory=territory)

@app.route("/download")
def view_download():
	url = request.args.get('url')
	try:
		territory = Territory(url)
	except Exception as e:
		flash("Exception: %s" % e)
		return redirect(".")
	out_buffer = StringIO()
	header = ["Salutation", "FirstName", "Name", "Address", "City", "State", "ZIP"]
	out = csv.DictWriter(out_buffer, fieldnames=header, quoting=csv.QUOTE_ALL)
	out.writeheader()
	for address in territory.addresses:
		m = re.match(r"^([^,]+), (.+)$", address.name)
		if m:
			formatted_name = "%s %s" % (m.group(2), m.group(1))
		else:
			formatted_name = address.name
		formatted_address = "%s %s" % (address.house_number, address.street)
		if address.apartment:
			formatted_address = "%s Apt. %s" % (formatted_address, address.apartment)
		out.writerow(dict(
			Salutation = "",
			FirstName = "",
			Name = formatted_name,
			Address = formatted_address,
			City = address.city,
			State = address.state,
			ZIP = address.postal_code
			))

	response = make_response(out_buffer.getvalue().encode('utf-8'))
	response.headers['Content-Type'] = 'text/csv'
	response.headers['Content-Disposition'] = 'attachment; filename="alba-territory-%s.csv"' % territory.number
	return response


