# encoding=utf-8

from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs, urlencode
import json
import re

from lxml.html import fromstring
import json5

class AlbaError(Exception):
	pass

class Address(dict):
	def __init__(self, address=None, **kwargs):
		super().__init__(**kwargs)

		if address is not None:
			m = re.match(r"^(\d+\S*)\s+(.+)$", address)
			assert m, address
			self["house_number"] = m.group(1)
			self["street"] = m.group(2)

	def __getattr__(self, name):
		return self[name] if name in self else ""

	# Class for table row
	def status_class(self):
		return "strikeout" if self.status not in ("Valid", "New", "") else ""

	# Parse the name field and return a list of individual names
	def names_list(self):
		name_parts = re.split(r"\s*[,&]\s*", self.name)
		#print("name_parts:", name_parts)
		if len(name_parts) < 2:
			return [self.name]
		names = []
		for given_name in name_parts[1:]:
			names.append("%s %s" % (given_name, name_parts[0]))
		return names

	# Format address for printing
	def street_address(self):
		return "%s %s" % (self.house_number, self.street)
	def city_state(self):
		return "%s, %s" % (self.city, self.state)

class Territory(object):
	user_agent = "Mozilla/5.0"
	per_page = 25

	# For converting the numberic status values in the locations structure to the strings used in the HTML table
	xlate_status = {
		1: "New",
		2: "Valid",
		3: "Do not call",
		4: "Moved",
		5: "Duplicate",
		6: "Not valid",
		}

	def __init__(self, url, load_all=False):
		self.load(url, load_all)

	def get_data(self, url):
		"""Request the territory, extract the data from a <script> in the HTML page"""
		response = urlopen(Request(
			url,
			headers = {"User-Agent": self.user_agent}
			))
		for line in response:
			line = line.decode()
			m = re.match(r"^\s+data: (\[.+\]),$", line)
			if m:
				data = json5.loads(m.group(1))
				return data[2]["data"]
		raise AlbaError("No data")
		
	def load(self, url:str, load_all:bool):
		"""Load the territory"""

		data = self.get_data(url)

		territory = data["territory"]
		self.number = territory["number"]
		self.description = territory["description"]
		self.notes = territory["notes"]

		# Create a list of markers starting with the alphabet, then AA, AB, AC, etc.
		alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
		marker_letters = alphabet[:]
		for letter1 in alphabet:
			for letter2 in alphabet:
				marker_letters.append(letter1 + letter2)

		self.addresses = []
		self.markers = []
		point_to_marker = {}
		for address in data["addresses"]:
			status = address["status"]
			status = self.xlate_status.get(status,status)

			if status in ("New", "Valid"):
				point = (address["location_lat"], address["location_lng"])
				marker = point_to_marker.get(point)
				if marker is None:
					marker = point_to_marker[point] = marker_letters[len(point_to_marker)]
				self.markers.append({
					"letter": marker,
					"point": point,
					})
			else:
				marker = None

			self.addresses.append(Address(
				id = address["id"],
				marker = marker,
				status = status,
				language = address["language_name"],
				name = address["full_name"],
				apartment = address["suite"],
				address = address["address"],
				city = address["city"],
				state = address["province"],
				postal_code = address["postcode"],
				phone = address["telephone"],
				notes = address["notes"],
				))

		self.border = [(lat, lng) for lng, lat in territory["border"]["coordinates"][0]]

	def npages(self):
		npages = int((len(self.addresses) + self.per_page - 1) / self.per_page)
		return npages

	def pages(self):
		addresses = self.addresses
		while len(addresses) > self.per_page:
			yield addresses[:self.per_page]
			addresses = addresses[self.per_page:]
		while len(addresses) < self.per_page:
			addresses.append(Address())
		yield addresses

