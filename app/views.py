from flask import request, render_template, redirect, flash, make_response
import csv
from io import StringIO
import re
from . import app
from .alba import Territory

@app.route("/")
def view_index():
	return render_template("index.html")

# Get the territory from Alba, return the list of addresses in CSV format
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

# Get the territory from Alba, return a web pages with a LeafletJS map
# and a table of addresses
@app.route("/print")
def view_print():
	url = request.args.get('url')
	try:
		territory = Territory(url)
		territory.per_page = 30
	except Exception as e:
		#raise
		flash("Сбой: %s" % e)
		return redirect(".")
	return render_template("print.html", territory=territory)

# Get the territory from Alba, return a table of addresses with links
# to an online directory.
@app.route("/research")
def view_research():
	url = request.args.get('url')
	try:
		territory = Territory(url, load_all=True)
	except Exception as e:
		flash("Exception: %s" % e)
		return redirect(".")
	return render_template("research.html", territory=territory)

# Get the territory from Alba, return the border polygon in JSON format
@app.route("/json")
def view_json():
	url = request.args.get('url')
	territory = Territory(url)
	return {
		'number': territory.number,
		'description': territory.description,
		'notes': territory.notes,
		'addresses': territory.addresses,
		'border': territory.border
		}

# This is unfinished
@app.route("/edit")
def view_edit():
	data = Territory.get(Territory.ajax_url, dict(
		territory = request.args.get('territory'),
		cmd = "edit",
		id = request.args.get('id')
		))
	response = make_response(data['data']['address'])
	response.headers['Content-Type'] = 'text/html'
	return response

