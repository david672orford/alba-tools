"""Simple Alba client using the Mobile URL"""

from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs, quote
from urllib.error import HTTPError
import re
import json

import json5

class AlbaError(Exception):
	pass

class Enum:
	def __init__(self, init):
		self.names = dict()
		self.ids = dict()
		for name, id in init.items():
			self.put(id, name)
	def put(self, id:int, name:str) -> None:
		self.names[id] = name
		self.ids[name] = id
	def get_name(self, id:int) -> str:
		return self.names[id]
	def get_id(self, name:str) -> int:
		return self.ids[name]

status_enum = Enum({
	"Unspecified": 0,
	"New": 1,
	"Valid": 2,
	"Do not call": 3,
	"Moved": 4,
	"Duplicate": 5,
	"Not valid": 6,
	})

language_enum = Enum({
	"None": 0,
	#"Russian": 2,		# disabled because now loaded from Alba's response
	#"French": 3,
	#"English": 10,
	#"Spanish": 16,
	#"Polish": 36,
	#"Ukrainian": 37,
	#"Moldovan": 111,
	})

class AlbaAddress:
	"""Store an address loaded from Alba"""

	# Our names for Alba's data fields
	alba_id: int|None
	marker: str
	_status: int
	_language: int
	name: str
	apartment: str
	address: str
	city: str
	state: str
	postal_code: str
	telephone: str
	notes: str
	lat: float
	lon: float


	def __init__(self, **kwargs):
		for attr_name, attr_type in self.__class__.__annotations__.items():
			value = kwargs.get(attr_name)
			if value is not None:
				if not isinstance(value, attr_type):
					raise TypeError(f"{attr_name}: {type(value)}")
			setattr(self, attr_name, value)

		# Split address into house number and street
		if self.address is not None:
			m = re.match(r"^(\d+\S*)\s+(.+)$", self.address)
			if m:
				self.house_number, self.street = m.groups()
			else:
				self.house_number = ""
				self.street = self.address
		elif "house_number" in kwargs and "street" in kwargs:
			self.house_number = kwargs["house_number"]
			self.street = kwargs["street"]
			self.address = f"{self.house_number} {self.street}"
		else:
			self.house_number = self.street = None

	def __str__(self):
		return f"<AlbaAddress alba_id={self.alba_id} status={repr(self.status)} language={repr(self.language)} name={repr(self.name)}>"

	# Status as a string
	@property
	def status(self):
		return status_enum.get_name(self._status)
	@status.setter
	def status(self, status:str):
		self._status = status_enum.get_id(status)

	# Language as a string
	@property
	def language(self):
		return language_enum.get_name(self._language)
	@language.setter
	def language(self, language:str):
		self._language = language_enum.get_id(language)

	# Users sometimes enter names in the form "Surname, Givenname1, Givenname2".
	# This splits it into ["Surname, Givenname1", "Surname, Givenname2"].
	def names_list(self):
		"""Parse the name field and return a list of individual names"""
		name_parts = re.split(r"\s*[,&]\s*", self.name)
		#print("name_parts:", name_parts)
		if len(name_parts) < 2:
			return [self.name]
		names = []
		for given_name in name_parts[1:]:
			names.append("%s %s" % (given_name, name_parts[0]))
		return names

class Markers(list):
	"""Assign alphabetical map markers"""
	def __init__(self):
		super().__init__()
		# Create a list of markers starting with the alphabet, then
		# AA, AB, AC, etc., ending with ZZ.
		alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
		marker_letters = alphabet[:]
		for letter1 in alphabet:
			for letter2 in alphabet:
				marker_letters.append(letter1 + letter2)
		self.marker_letters = marker_letters
		self.point_to_marker = {}
	def get_marker(self, point):
		marker = self.point_to_marker.get(point)
		if marker is None:
			marker = self.point_to_marker[point] = self.marker_letters[len(self.point_to_marker)]
		self.append({
			"letter": marker,
			"point": point,
			})
		return marker

class AlbaTerritory(list):
	user_agent = "Mozilla/5.0"

	def __init__(self, url:str, noload=False):
		super().__init__()
		self.url = url

		p = urlparse(self.url)
		print("Alba: URL:", p)
		if p.netloc != "www.mcmxiv.com":
			raise AlbaError("Not an Alba URL")

		if p.path == "/alba/mobile":	# URL format prior to May 2026
			q = parse_qs(p.query)
			self.url = f"{p.scheme}://{p.netloc}/alba/m/{q['territory'][0]}"
		elif p.path.startswith("/alba/print/territory/"):
			q = parse_qs(p.query)
			self.url = f"{p.scheme}://{p.netloc}/alba/m/{quote(q['token'][0])}"

		if self.url != url:
			print("Currected URL:", self.url)

		if not noload:
			self.load(url)

	def __str__(self):
		return f"<AlbaTerritory {self.number}: {len(self)} addresses, {len(self.border)} polygon points>"

	def get_data(self, url:str):
		"""Request the territory, extract the data from a <script> in the HTML page"""
		try:
			response = urlopen(Request(
				url,
				headers = {"User-Agent": self.user_agent}
				))
		except Exception as e:
			raise AlbaError(f"Fetch failed: {str(e)}")
		for line in response:
			line = line.decode()
			m = re.match(r"^\s+data: (\[.+\]),$", line)
			if m:
				data = json5.loads(m.group(1))
				#with open("data.txt","w") as fh:
				#	fh.write(m.group(1))
				#with open("data.json","w") as fh:
				#	json.dump(data, fh, indent=2)
				return data[2]["data"]
		raise AlbaError("No data")

	def load(self, url:str):
		"""Load the territory from the mobile URL provided"""

		data = self.get_data(url)

		territory = data["territory"]
		self.number = territory["number"]
		self.description = territory["description"]
		self.border = [(lat, lng) for lng, lat in territory["border"]["coordinates"][0]]
		self.notes = territory["notes"] or ""
		self.url = url

		for language in data["languages"]:
			language_enum.put(language["id"], language["language"])

		self.markers = Markers()
		for address in data["addresses"]:

			# If this address should be visited, assign it a marker.
			if address["status"] in (1, 2): # New or Valid
				marker = self.markers.get_marker((address["location_lat"], address["location_lng"]))
			else:
				marker = ""

			self.append(AlbaAddress(
				alba_id = address["id"],
				marker = marker,
				_status = address["status"],
				_language = address["language_id"],
				name = address["full_name"],
				apartment = address["suite"] or "",
				address = address["address"],
				city = address["city"],
				state = address["province"],
				postal_code = address["postcode"],
				telephone = address["telephone"],
				notes = address["notes"],
				lat = float(address["location_lat"]),
				lon = float(address["location_lng"]),
				))

	alba_save_keys = {
		"alba_id": "id",
		"name": "full_name",
		"apartment": "suite",
		"address": "address",
		"city": "city",
		"state": "province",
		"postal_code": "postcode",
		"telephone": "telephone",
		"notes": "notes",
		"_status": "status",
		"_language": "language_id",
		"lat": "location_lat",
		"lon": "location_lng",
		}

	def address_save(self, address:AlbaAddress):
		assert isinstance(address.alba_id, int)
		data = {
			"action": "address_save",
			}
		for name, alba_key in self.alba_save_keys.items():
			value = getattr(address, name)
			if value is not None:
				data[alba_key] = value
		self.api_call(data)

	def address_add(self, address:AlbaAddress):
		assert address.alba_id is None
		data = {
			"action": "address_add",
			}
		for name, alba_key in self.alba_save_keys.items():
			value = getattr(address, name)
			if value is not None:
				data[alba_key] = value
		response = self.api_call(data)
		return response["id"]

	def api_call(self, data:dict) -> dict:
		print("Alba: API request", data)
		try:
			response = urlopen(Request(
				self.url + "/api",
				headers = {
					"User-Agent": self.user_agent,
					"Content-Type": "application/json",
					},
				data = json.dumps(data).encode("utf-8"),
				method = "POST",
				))
		except HTTPError as e:
			if e.code == 410:	# Gone
				raise AlbaError("Alba link is no longer valid")
			else:
				raise AlbaError(f"API call failed: {e}")
		response_data = json.loads(response.read().decode("utf-8"))
		if response_data.get("success") is not True:
			raise AlbaError("API call failed")
		print("Alba: API response:", response_data["data"])
		return response_data["data"]
