# encoding=utf-8

from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs, urlencode
from lxml.html import fromstring
import json
import re

class Address(dict):
	def __init__(self, first_address, **kwargs):
		super().__init__(**kwargs)

		if 'address' in self:
			# 42, 123 Main Street, Manchester, CT, 06040
			address = self.address.split(", ")
			#print("address:", address)

			# Take ZIP code off right (if there is one)
			self['postal_code'] = address.pop(-1) if re.match(r'^[0-9-]+$', address[-1]) else ""

			if len(address) >= 3:		# city and state present
				self['state'] = address.pop(-1)
				self['city'] = address.pop(-1)
			else:
				self['state'] = first_address['province']
				self['city'] = first_address['city']
			self['apartment'] = address.pop(0) if len(address) == 2 else ""
			self['house_number'], self['street'] = address[0].split(" ",1)

	def __getattr__(self, name):
		return self[name] if name in self else ""

	# Class for table row
	def status_class(self):
		return "strikeout" if self.status in ("Moved", "Not valid") else ""

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

	def __init__(self, url):

		# Extract the territory access code from the URL of the mobile version.
		parsed_url = urlparse(url)
		assert parsed_url.path == "/alba/mobile/", parsed_url.path
		self.territory_access_code = parse_qs(parsed_url.query)['territory'][0]

		self.load(url)

	def load(self, url):

		# Send AJAX request. Parse the JSON response.
		response = urlopen(Request(
			self.ajax_url + "?" + urlencode({
				'territory': self.territory_access_code,
				'nv': '',
				}),
			headers={'User-Agent': self.user_agent}
			))
		data = json.loads(response.read())['data']

		# Process the HTML table of addresses which is embedded in the JSON response.
		tree = fromstring(data['html'])
		self.addresses = []
		first_address = None
		for tr in tree.xpath("//tbody[@id='addresses']/tr"):
			id = tr.attrib['id'][2:]
			if first_address is None:
				first_address = self.load_address(id)

			td = tr.xpath("./td")
			assert len(td) == 2

			where = td[0].xpath(".//span[@class='where']")[0]
			notes = where.xpath("./small")
			if len(notes) > 0:
				notes = re.sub(r'^“(.+)”$', lambda m: m.group(1), notes[0].text)
			else:
				notes = ""

			call = td[1].xpath(".//a[@class='cmd-call']")
			if len(call) > 0:
				phone = re.sub(r'^tel://(.+)$', lambda m: m.group(1), call[0].attrib['rel'])
			else:
				phone = ""

			row = Address(
				first_address = first_address,
				id = id,
				status = td[0].xpath("./span")[0].text,
				language = td[0].xpath("./span[@class='badge']")[0].text,
				name = td[0].xpath("./strong[@class='who']")[0].text,
				address = where.text.strip(),
				phone = phone,
				notes = notes,
				)
			self.addresses.append(row)

		self.border = data['border']
		self.locations = data['locations']

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
			addresses.append(Address())
		yield addresses

	def locations_as_json(self):
		return json.dumps(self.locations)

	def border_as_json(self):
		return json.dumps(self.border)

