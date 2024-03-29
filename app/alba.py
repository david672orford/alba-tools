# encoding=utf-8

from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs, urlencode
from lxml.html import fromstring
import json
import re

class AlbaError(Exception):
	pass

class Address(dict):
	def __init__(self, first_address, **kwargs):
		super().__init__(**kwargs)

		if 'address' in self:
			# 42, 123 Main Street, Manchester, CT, 06040
			address = self.address.split(", ")
			#print("address:", address)

			# Take ZIP code off right (if there is one)
			self['postal_code'] = address.pop(-1) if re.match(r'^[0-9-]+$', address[-1]) else ""

			if re.search(r"^[A-Z][A-Z]$", address[-1]):		# 42, 123 Main Street, Manchester, CT
				self['state'] = address.pop(-1)
				self['city'] = address.pop(-1)
			elif not re.search(r"^\d", address[-1]):		# 42, 123 Main Street, Westfield
				self['state'] = first_address['province']
				self['city'] = address.pop(-1)
			else:											# 42, 123 Main Street (no city)
				self['state'] = first_address['province']
				self['city'] = first_address['city']

			self['apartment'] = address.pop(0) if len(address) == 2 else ""
			if " " in address[0]:
				self['house_number'], self['street'] = address[0].split(" ",1)
			else:
				self['house_number'] = ""
				self['street'] = address[0]

	def __getattr__(self, name):
		return self[name] if name in self else ""

	# Class for table row
	def status_class(self):
		return "strikeout" if self.status not in ("Valid", "New", "") else ""

	# Parse the name field and return a list of individual names
	def names_list(self):
		name_parts = re.split(r'\s*[,&]\s*', self.name)
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
	ajax_url = "https://www.mcmxiv.com/alba/mobile/ts"

	def __init__(self, url, load_all=False):

		# Extract the territory access code from the URL of the mobile version.
		parsed_url = urlparse(url)
		assert parsed_url.path in ("/alba/mobile", "/alba/mobile/"), "Incorrect path: %s" % parsed_url.path
		self.territory_access_code = parse_qs(parsed_url.query)['territory'][0]

		self.load(url, load_all)

	# Send AJAX request to Alba. Parse the JSON response.
	@staticmethod
	def get(url, query):
		response = urlopen(Request(
			Territory.ajax_url + "?" + urlencode(query),
			headers={'User-Agent': Territory.user_agent}
			))
		data = json.loads(response.read())
		#print(json.dumps(data, indent=2))
		return data

	def load(self, url, load_all):

		data = self.get(url, dict(
			territory = self.territory_access_code,
			nv = ''
			))
		if data['error']:
			raise AlbaError(data['error'])
		data = data['data']

		metadata = data['meta']['territory']
		self.number = metadata['number']
		self.description = metadata['description']
		self.notes = metadata['territory_notes']

		# For converting the numberic status values in the locations structure to the strings used in the HTML table
		xlate_status = {
			1: 'New',
			2: 'Valid',
			3: 'Do not call',
			4: 'Moved',
			5: 'Duplicate',
			6: 'Not valid',
			}

		# Create a list of markers starting with the alphabet, then AA, AB, AC, etc.
		alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
		marker_letters = alphabet[:]
		for letter1 in alphabet:
			for letter2 in alphabet:
				marker_letters.append(letter1 + letter2)

		# Assign a marker to each location which needs to be visited
		self.markers = []
		point_to_letter = {}
		id_to_letter = {}
		for id, ldata in data['locations'].items():
			status = ldata['st']
			status = xlate_status.get(status,status)
			if status in ("New", "Valid"):
				point = (ldata['la'], ldata['ln'])
				letter = point_to_letter.get(point)
				if letter is None:
					letter = point_to_letter[letter] = marker_letters[len(point_to_letter)]
				self.markers.append({
					'letter': letter,
					'point': point,
					})
				id_to_letter[id] = letter

		# Process the HTML table of addresses which is embedded in the JSON response.
		tree = fromstring(data['html'])
		self.addresses = []
		first_address = None
		tbody_i = 0
		for tbody in tree.xpath("//tbody[@class='addresses']"):
			for tr in tbody.xpath("./tr"):
				id = tr.attrib['id'][2:]
				if first_address is None:
					first_address = self.load_address(id)
	
				td = tr.xpath("./td")
				assert len(td) == (2 - tbody_i), "Incorrect number of cells"
	
				status = td[0].xpath("./span")[0].text
				if not load_all and status not in ("New", "Valid", "Do not call"):
					continue

				notes = ""
				phone = ""
				if tbody_i == 0:
					who = td[0].xpath("./strong[@class='who']")[0]
					where = td[0].xpath(".//span[@class='where']")[0]
					small = where.xpath("./small")
					if len(small) > 0:
						notes = re.sub(r'^“(.+)”$', lambda m: m.group(1), small[0].text)
					call = td[1].xpath(".//a[@class='cmd-call']")
					if len(call) > 0:
						phone = re.sub(r'^tel://(.+)$', lambda m: m.group(1), call[0].attrib['rel'])
						m = re.match(r'^(\d\d\d)(\d\d\d)(\d\d\d\d)$', phone)
						if m:
							phone = "(%s) %s-%s" % m.groups()
				else:		# "Also in this area"
					who = td[0].xpath("./strong")[0]
					where = td[0].xpath(".//span")[2]
	
				row = Address(
					first_address = first_address,
					id = id,
					marker = id_to_letter.get(id),
					status = status,
					language = td[0].xpath("./span[@class='badge']")[0].text,
					name = who.text,
					address = where.text.strip(),
					phone = phone,
					notes = notes,
					)
				self.addresses.append(row)

			if not load_all:
				break

			tbody_i += 1

		self.border = data['border']

	# Load an address as if the user had chosen "Edit" from the menu.
	def load_address(self, id):
		response = urlopen(Request(
			self.ajax_url + "?" + urlencode({
				'territory': self.territory_access_code,
				'nv': '',
				'cmd': 'edit',
				'id': id
				}),
			headers={'User-Agent': self.user_agent}
			))
		addr_data = json.loads(response.read())['data']
		addr_tree = fromstring(addr_data['address'])
		address = {}
		for control in addr_tree.xpath("//input"):
			address[control.attrib['name']] = control.attrib['value']
		return address

	def npages(self):
		npages = int((len(self.addresses) + self.per_page - 1) / self.per_page)
		return npages

	def pages(self):
		addresses = self.addresses
		while len(addresses) > self.per_page:
			yield addresses[:self.per_page]
			addresses = addresses[self.per_page:]
		while len(addresses) < self.per_page:
			addresses.append(Address(None))
		yield addresses

