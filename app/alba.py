from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs, urlencode
from lxml.html import fromstring
import json
import re

class Address(dict):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		if 'address' in self:
			address = self.address.split(", ")
			print(address)
			self.postal_code = address.pop(-1) if re.match(r'^[0-9-]+$', address[-1]) else ""
			self.apartment = address.pop(0) if len(address) == 4 else ""
			street, self.city, self.state = address
			self.house_number, self.street = street.split(" ",1)
	def __getattr__(self, name):
		return self[name] if name in self else ""

class Territory(object):
	user_agent = "Mozilla/5.0"
	per_page = 25

	def __init__(self, url):
		parsed_url = urlparse(url)
		territory = parse_qs(parsed_url.query)['territory'][0]
		new_url = "https://www.mcmxiv.com/alba/print-mk?territory=%s&%s" % (
			territory,
			'address_only=0&m=1&o=1&l=1&d=1&c_n=1&c_t=1&c_l=1&c_nt=1&g=0&cl=1&clss=1&coop=0&st=1%2C2%2C3&nv'
			)
		assert new_url == url

		response = urlopen(Request(new_url, headers={'User-Agent': self.user_agent}))
		tree = fromstring(response.read())

		strong = tree.xpath("//h1/strong")[0]
		self.number = strong.text
		self.description = strong.tail.strip()

		self.addresses = []
		tbody = tree.xpath("//table[@class='addresses']/tbody")[0]
		for tr in tbody:
			cells = tr.xpath("./td")
			row = Address(
				marker = cells[0][0].text,
				id = cells[0][1].text,
				status = cells[1].text_content(),
				language = cells[2].text,
				name = cells[3][0].text,
				phone = cells[3][1].text or "",
				address = cells[4].text,
				notes = cells[5].text or ""
				)
			self.addresses.append(row)

		script = tree.xpath("//body/script")[0].text
		lines = script.split("\n")

		assert lines[1].startswith("var border = [") and lines[1][-2:] == '];'
		self.border = json.loads(lines[1][13:-1])

		assert lines[2].startswith("var locations = [") and lines[2][-2:] == '];'
		self.locations = json.loads(lines[2][16:-1])

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

