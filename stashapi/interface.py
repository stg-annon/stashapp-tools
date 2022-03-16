import re, sys
from collections import defaultdict

import requests
from requests.structures import CaseInsensitiveDict 

from enum import IntEnum

from . import stash_fragments
from . import log as stash_logger

class PhashDistance(IntEnum):
	EXACT = 0
	HIGH = 4
	MEDIUM = 8
	LOW = 10

class StashInterface:
	port = ""
	url = ""
	headers = {
		"Accept-Encoding": "gzip, deflate",
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Connection": "keep-alive",
		"DNT": "1"
	}
	cookies = {}

	def __init__(self, conn:dict={}, fragments:dict={}):
		global log

		conn = CaseInsensitiveDict(conn)

		log = conn.get("Logger", stash_logger)

		# Session cookie for authentication
		self.cookies = {}
		if conn.get("SessionCookie"):
			self.cookies['session'] = conn['SessionCookie']['Value']

		scheme = conn.get('Scheme', 'http')
		domain = conn.get('Domain', 'localhost')

		self.port = conn.get('Port', 9999)

		# Stash GraphQL endpoint
		self.url = f'{scheme}://{domain}:{self.port}/graphql'
		log.debug(f"Using stash GraphQl endpoint at {self.url}")

		try:
			# test query to ensure good connection
			self.call_gql("query Configuration {configuration{general{stashes{path}}}}")
		except Exception:
			log.error(f"Could not connect to Stash at {self.url}")
			sys.exit()

		self.fragments = fragments
		self.fragments.update(stash_fragments.GQL_FRAGMENTS)

		# create flags
		self.create_on_missing_tag = False
		self.create_on_missing_performer = False

	def __resolveFragments(self, query):

		fragmentReferences = list(set(re.findall(r'(?<=\.\.\.)\w+', query)))
		fragments = []
		for ref in fragmentReferences:
			fragments.append({
				"fragment": ref,
				"defined": bool(re.search("fragment {}".format(ref), query))
			})

		if all([f["defined"] for f in fragments]):
			return query
		else:
			for fragment in [f["fragment"] for f in fragments if not f["defined"]]:
				if fragment not in self.fragments:
					raise Exception(f'GraphQL error: fragment "{fragment}" not defined')
				query += self.fragments[fragment]
			return self.__resolveFragments(query)

	def __callGraphQL(self, query, variables=None):

		query = self.__resolveFragments(query)

		json_request = {'query': query}
		if variables is not None:
			json_request['variables'] = variables

		response = requests.post(self.url, json=json_request, headers=self.headers, cookies=self.cookies)
		
		if response.status_code == 200:
			result = response.json()

			if result.get("errors"):
				for error in result["errors"]:
					log.error(f"GraphQL error: {error}")
			if result.get("error"):
				for error in result["error"]["errors"]:
					log.error(f"GraphQL error: {error}")
			if result.get("data"):
				scraped_markers = defaultdict(lambda: None)
				scraped_markers.update(result)
				return scraped_markers['data']
		elif response.status_code == 401:
			sys.exit("HTTP Error 401, Unauthorized. Cookie authentication most likely failed")
		else:
			raise ConnectionError(
				"GraphQL query failed:{} - {}. Query: {}. Variables: {}".format(
					response.status_code, response.content, query, variables)
			)

	def __match_alias_item(self, search, items):
		item_matches = {}
		for item in items:
			if re.match(rf'{search}$', item["name"], re.IGNORECASE):
				log.debug(f'matched "{search}" to "{item["name"]}" ({item["id"]}) using primary name')
				item_matches[item["id"]] = item
			if not item["aliases"]:
				continue
			for alias in item["aliases"]:
				if re.match(rf'{search}$', alias.strip(), re.IGNORECASE):
					log.info(f'matched "{search}" to "{item["name"]}" ({item["id"]}) using alias')
					item_matches[item["id"]] = item
		return list(item_matches.values())

	def __match_performer_alias(self, search, performers):
		item_matches = {}
		for item in performers:
			if re.match(rf'{search}$', item["name"], re.IGNORECASE):
				log.info(f'matched "{search}" to "{item["name"]}" ({item["id"]}) using primary name')
				item_matches[item["id"]] = item
			if not item["aliases"]:
				continue
			for alias in item["aliases"]:
				parsed_alias = alias.strip()
				if ":" in alias:
					parsed_alias = alias.split(":")[-1].strip()
				if re.match(rf'{search}$', parsed_alias, re.IGNORECASE):
					log.info(f'matched "{search}" to "{item["name"]}" ({item["id"]}) using alias')
					item_matches[item["id"]] = item
		return list(item_matches.values())

	def call_gql(self, query, variables={}):
		return self.__callGraphQL(query, variables)

	def graphql_configuration(self):
		query = """
			query Configuration {
				configuration {
					...ConfigData
				}
			}
		"""
		
		result = self.__callGraphQL(query)
		return result['configuration']

	def metadata_scan(self, paths=[]):
		query = """
		mutation metadataScan($input:ScanMetadataInput!) {
			metadataScan(input: $input)
		}
		"""
		variables = {
			'input': {
				'paths' : paths,
				'useFileMetadata': False,
				'stripFileExtension': False,
				'scanGeneratePreviews': False,
				'scanGenerateImagePreviews': False,
				'scanGenerateSprites': False,
				'scanGeneratePhashes': True
			}
		}
		result = self.__callGraphQL(query, variables)
		return result

	# Tag CRUD
	def find_tag(self, name_in, create=False):
		name = name_in
		if isinstance(name, dict):
			if not name.get("name"):
				return
			name = name["name"]

		if not isinstance(name, str):
			log.warning(f'find_tag expects str or dict not {type(name_in)} "{name_in}"')
			return

		for tag in self.find_tags(q=name):
			if tag["name"].lower() == name.lower():
				return tag
			if any(name.lower() == a.lower() for a in tag["aliases"] ):
				return tag
		if create:
			return self.create_tag({"name":name})
	def create_tag(self, tag):
		query = """
			mutation tagCreate($input:TagCreateInput!) {
				tagCreate(input: $input){
					...stashTag
				}
			}
		"""
		variables = {'input': tag}
		result = self.__callGraphQL(query, variables)
		return result["tagCreate"]
	#TODO update_tag
	def destroy_tag(self, tag_id):
		query = """
			mutation tagDestroy($input: TagDestroyInput!) {
				tagDestroy(input: $input)
			}
		"""
		variables = {'input': {
			'id': tag_id
		}}

		self.__callGraphQL(query, variables)

	# Tags CRUD
	def find_tags(self, q="", f={}):
		query = """
			query FindTags($filter: FindFilterType, $tag_filter: TagFilterType) {
				findTags(filter: $filter, tag_filter: $tag_filter) {
					count
					tags {
						...stashTag
					}
				}
			}
		"""

		variables = {
		"filter": {
			"direction": "ASC",
			"per_page": -1,
			"q": q,
			"sort": "name"
		},
		"tag_filter": f
		}
		
		result = self.__callGraphQL(query, variables)
		return result["findTags"]["tags"]

	# Performer CRUD
	def find_performer(self, performer_data, create_missing=False):
		if isinstance(performer_data, str):
			performer_data["name"] = performer_data
		if not performer_data.get("name"):
			return None

		name = performer_data["name"]
		name = name.strip()

		performer_data["name"] = name

		performers = self.find_performers(q=name)

	
		for p in performers:
			if not p.get("aliases"):
				continue
			alias_delim = re.search(r'(\/|\n|,|;)', p["aliases"])
			if alias_delim:
				p["aliases"] = p["aliases"].split(alias_delim.group(1))
			elif len(p["aliases"]) > 0:
				p["aliases"] = [p["aliases"]]
			else:
				log.warning(f'Could not determine delim for aliases "{p["aliases"]}"')

		performer_matches = self.__match_performer_alias(name, performers)

		# none if multuple results from a single name performer
		if len(performer_matches) > 1 and name.count(' ') == 0:
			return None
		elif len(performer_matches) > 0:
			return performer_matches[0] 


		if create_missing:
			log.info(f'Create missing performer: "{name}"')
			return self.create_performer(performer_data)
	def create_performer(self, performer_data):
		query = """
			mutation($input: PerformerCreateInput!) {
				performerCreate(input: $input) {
					id
				}
			}
		"""

		variables = {'input': performer_data}

		result = self.__callGraphQL(query, variables)
		return result['performerCreate']['id']
	def update_performer(self, performer_data):
		query = """
			mutation performerUpdate($input:PerformerUpdateInput!) {
				performerUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': performer_data}

		result = self.__callGraphQL(query, variables)
		return result['performerUpdate']['id']
	#TODO delete performer

	# Performers CRUD
	def find_performers(self, q="", f={}):
		query =  """
			query FindPerformers($filter: FindFilterType, $performer_filter: PerformerFilterType) {
				findPerformers(filter: $filter, performer_filter: $performer_filter) {
					count
					performers {
						...stashPerformer
					}
				}
			}
		"""

		variables = {
			"filter": {
				"q": q,
				"per_page": -1,
				"sort": "name",
				"direction": "ASC"
			},
			"performer_filter": f
		}

		result = self.__callGraphQL(query, variables)
		return result['findPerformers']['performers']

	# Studio CRUD
	def find_studio(self, studio, create_missing=False, domain_pattern=r'[^.]*\.[^.]{2,3}(?:\.[^.]{2,3})?$'):
		if not studio.get("name"):
			return None

		name = studio["name"]

		studio_matches = []

		if re.match(domain_pattern, name):
			url_search = self.find_studios(f={
				"url":{ "value": name, "modifier": "INCLUDES" }
			})
			for s in url_search:
				if re.search(rf'{name}',s["url"]):
					log.info(f'matched "{name}" to {s["url"]} using URL')
					studio_matches.append(s)

		name_results = self.find_studios(q=name)
		studio_matches.extend(self.__match_alias_item(name, name_results))

		if len(studio_matches) > 1 and name.count(' ') == 0:
			return None
		elif len(studio_matches) > 0:
			return studio_matches[0] 

		if create_missing:
			log.info(f'Create missing studio: "{name}"')
			return self.create_studio(studio)
	def create_studio(self, studio):
		query = """
			mutation($name: String!) {
				studioCreate(input: { name: $name }) {
					id
				}
			}
		"""
		variables = {
			'name': studio['name']
		}

		result = self.__callGraphQL(query, variables)
		studio['id'] = result['studioCreate']['id']

		return self.update_studio(studio)
	def update_studio(self, studio):
		query = """
			mutation StudioUpdate($input:StudioUpdateInput!) {
				studioUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': studio}

		result = self.__callGraphQL(query, variables)
		return result["studioUpdate"]["id"]
	# TODO delete_studio()

	def get_studio(self, studio, get_root_parent=False):
		query =  """
		query FindStudio($studio_id: ID!) {
			findStudio(id: $studio_id) {
				...stashStudio
			}
		}
		"""
		variables = {
			"studio_id": studio.get("id")
		}
		result = self.__callGraphQL(query, variables)
		studio = result['findStudio']

		if get_root_parent and studio and studio.get("parent_studio"):
			return self.get_studio(studio["parent_studio"], get_root_parent=True)
		return studio
		

	def find_studios(self, q="", f={}):
		query =  """
		query FindStudios($filter: FindFilterType, $studio_filter: StudioFilterType) {
			findStudios(filter: $filter, studio_filter: $studio_filter) {
			count
			studios {
				...stashStudio
			}
			}
		}
		"""

		variables = {
			"filter": {
			"q": q,
			"per_page": -1,
			"sort": "name",
			"direction": "ASC"
			},
			"studio_filter": f
		}

		result = self.__callGraphQL(query, variables)
		return result['findStudios']['studios']

	# Movie CRUD
	def find_movie(self, movie, create_missing=False):

		name = movie["name"]
		movies = self.find_movies(q=name)

		movie_matches = self.__match_alias_item(name, movies)

		if len(movie_matches) > 0:
			if len(movie_matches) == 1:
				return movie_matches[0]
			else:
				log.warning(f'Too many matches for movie "{name}"')
				return None

		if create_missing:
			log.info(f'Creating missing Movie "{name}"')
			return self.create_movie(movie)
	def create_movie(self, movie):
		name = movie["name"]
		query = """
			mutation($name: String!) {
				movieCreate(input: { name: $name }) {
					id
				}
			}
		"""
		variables = {'name': name}
		result = self.__callGraphQL(query, variables)
		movie['id'] = result['movieCreate']['id']
		return self.update_movie(movie)
	def update_movie(self, movie):
		query = """
			mutation MovieUpdate($input:MovieUpdateInput!) {
				movieUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': movie}

		result = self.__callGraphQL(query, variables)
		return result['movieUpdate']['id']
	#TODO delete movie

	# Movies CRUD
	def find_movies(self, q="", f={}):
		query = """
			query FindMovies($filter: FindFilterType, $movie_filter: MovieFilterType) {
				findMovies(filter: $filter, movie_filter: $movie_filter) {
					count
					movies {
						...stashMovie
					}
				}
			}
		"""

		variables = {
			"filter": {
				"per_page": -1,
				"q": q
			},
			"movie_filter": f
		}
		
		result = self.__callGraphQL(query, variables)
		return result['findMovies']['movies']

	#Gallery CRUD
	# create_gallery() done by scan see metadata_scan()
	# TODO find_gallery()
	def update_gallery(self, gallery_data):
		query = """
			mutation GalleryUpdate($input:GalleryUpdateInput!) {
				galleryUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': gallery_data}

		result = self.__callGraphQL(query, variables)
		return result["galleryUpdate"]["id"]
	# TODO delete_gallery

	# BULK Gallery
	def find_galleries(self, q="", f={}):
		query = """
			query FindGalleries($filter: FindFilterType, $gallery_filter: GalleryFilterType) {
				findGalleries(gallery_filter: $gallery_filter, filter: $filter) {
					count
					galleries {
						...stashGallery
					}
				}
			}
		"""
		variables = {
			"filter": {
				"q": q,
				"per_page": -1,
				"sort": "path",
				"direction": "ASC"
			},
			"gallery_filter": f
		}

		result = self.__callGraphQL(query, variables)
		return result['findGalleries']['galleries']


	# Scene CRUD
	# create_scene() done by scan see metadata_scan()
	def find_scene(self, id:int):
		query = """
		query FindScene($scene_id: ID) {
			findScene(id: $scene_id) {
				...stashScene
			}
		}
		"""
		variables = {"scene_id": id}

		result = self.__callGraphQL(query, variables)
		return result['findScene']
	def update_scene(self, update_input):
		query = """
			mutation sceneUpdate($input:SceneUpdateInput!) {
				sceneUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': update_input}

		result = self.__callGraphQL(query, variables)
		return result["sceneUpdate"]["id"]
	def destroy_scene(self, scene_id, delete_file=False):
		query = """
		mutation SceneDestroy($input:SceneDestroyInput!) {
			sceneDestroy(input: $input)
		}
		"""
		variables = {
			"input": {
				"delete_file": delete_file,
				"delete_generated": True,
				"id": scene_id
			}
		}
			
		result = self.__callGraphQL(query, variables)
		return result['sceneDestroy']
	
	# BULK Scenes
	# scenes created by scan see metadata_scan()
	def find_scenes(self, f={}):
		query = """
		query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType, $scene_ids: [Int!]) {
			findScenes(filter: $filter, scene_filter: $scene_filter, scene_ids: $scene_ids) {
				count
				scenes {
					...stashScene
				}
			}
		}
		"""
		variables = {
			"filter": { "per_page": -1 },
			"scene_filter": f
		}
			
		result = self.__callGraphQL(query, variables)
		return result['findScenes']['scenes']
	def update_scenes(self, updates_input):
		query = """
			mutation BulkSceneUpdate($input:BulkSceneUpdateInput!) {
				bulkSceneUpdate(input: $input) {
					id
				}
			}
		"""
		variables = {'input': updates_input}

		result = self.__callGraphQL(query, variables)
		return result["bulkSceneUpdate"]
	def destroy_scenes(self, scene_ids, delete_file=False):
		query = """
		mutation ScenesDestroy($input:ScenesDestroyInput!) {
			scenesDestroy(input: $input)
		}
		"""
		variables = {
			"input": {
				"delete_file": delete_file,
				"delete_generated": True,
				"ids": scene_ids
			}
		}
			
		result = self.__callGraphQL(query, variables)
		return result['scenesDestroy']

	def merge_scene_markers(self, target_scene_id: int, source_scene_ids: list):

		def get_scene_markers(scene_id) -> list:
			query = """
				query GetSceneMarkers($scene_id: ID) {
					findScene(id: $scene_id) {
						scene_markers {
							title
							seconds
							primary_tag { id }
							tags { id }
						}
					}
				}
			"""
			variables = { "scene_id": scene_id }
			return self.__callGraphQL(query, variables)["findScene"]["scene_markers"]

		def create_scene_marker(marker_create_input:dict):
			query = """
				mutation SceneMarkerCreate($marker_input: SceneMarkerCreateInput!) {
					sceneMarkerCreate(input: $marker_input) {
						id
					}
				}
			"""
			variables = { "marker_input": marker_create_input }
			return self.__callGraphQL(query, variables)["sceneMarkerCreate"]


		existing_marker_timestamps = [marker["seconds"] for marker in get_scene_markers(target_scene_id)]

		markers_to_merge = []
		for source_scene_id in source_scene_ids:
			markers_to_merge.extend(get_scene_markers(source_scene_id))

		created_markers = []
		for marker in markers_to_merge:
			if marker["seconds"] in existing_marker_timestamps:
				# skip existing marker
				# TODO merge missing data between markers
				continue
			marker_id = create_scene_marker({
				"title": marker["title"],
				"seconds": marker["seconds"],
				"scene_id": target_scene_id,
				"primary_tag_id": marker["primary_tag"]["id"],
				"tag_ids": [t["id"] for t in marker["tags"]],
			})
			created_markers.append(marker_id)
		return created_markers

	def merge_scenes(self, target_scene_id:int, source_scene_ids:list):
		def get_min_scene_meta(source_id):
			query = """
				query FindScene($scene_id: ID) {
					findScene(id: $scene_id) {
						title
						details
						url
						date
						rating
						studio { id }
						galleries { id }
						performers { id }
						tags { id }
						movies { movie { id } scene_index }
					}
				}
			"""
			variables = { "scene_id": source_id }
			return self.__callGraphQL(query, variables)["findScene"]

		merged_markers = self.merge_scene_markers(target_scene_id, source_scene_ids)
		log.info(f"Merged {len(merged_markers)} markers from {source_scene_ids} to {target_scene_id}")

		target_meta = get_min_scene_meta(target_scene_id)

		for source_id in source_scene_ids:
			source_data = get_min_scene_meta(source_id)
			scene_update = {
				"ids": [target_scene_id],
				"gallery_ids": {
					 "ids": [ g["id"] for g in source_data["galleries"] ],
					 "mode": "ADD"
				},
				"performer_ids": {
					 "ids": [ p["id"] for p in source_data["performers"] ],
					 "mode": "ADD"
				},
				"tag_ids": {
					 "ids": [ t["id"] for t in source_data["tags"] ],
					 "mode": "ADD"
				},
				"movie_ids": {
					 "ids": [ sm["movie"]["id"] for sm in source_data["movies"] ],
					 "mode": "ADD"
				},
			}
			if source_data.get("studio"):
				scene_update["studio_id"] = source_data["studio"]["id"]
			if source_data.get("date") and target_meta.get("date", "9999-99-99") > source_data["date"]:
				scene_update["date"] = source_data["date"]
			if source_data.get("url"):
				scene_update["url"] = source_data["url"]
				
			updated_scene_ids = self.update_scenes(scene_update)

		return updated_scene_ids

	# Scraper Operations
	def reload_scrapers(self):
		query = """ 
			mutation ReloadScrapers {
				reloadScrapers
			}
		"""
		
		result = self.__callGraphQL(query)
		return result["reloadScrapers"]
	
	def list_performer_scrapers(self, type):
		query = """
		query ListPerformerScrapers {
			listPerformerScrapers {
			  id
			  name
			  performer {
				supported_scrapes
			  }
			}
		  }
		"""
		ret = []
		result = self.__callGraphQL(query)
		for r in result["listPerformerScrapers"]:
			if type in r["performer"]["supported_scrapes"]:
				ret.append(r["id"])
		return ret
	def list_scene_scrapers(self, type):
		query = """
		query listSceneScrapers {
			listSceneScrapers {
			  id
			  name
			  scene{
				supported_scrapes
			  }
			}
		  }
		"""
		ret = []
		result = self.__callGraphQL(query)
		for r in result["listSceneScrapers"]:
			if type in r["scene"]["supported_scrapes"]:
				ret.append(r["id"])
		return ret
	def list_gallery_scrapers(self, type):
		query = """
		query ListGalleryScrapers {
			listGalleryScrapers {
			  id
			  name
			  gallery {
				supported_scrapes
			  }
			}
		  }
		"""
		ret = []
		result = self.__callGraphQL(query)
		for r in result["listGalleryScrapers"]:
			if type in r["gallery"]["supported_scrapes"]:
				ret.append(r["id"])
		return ret
	def list_movie_scrapers(self, type):
		query = """
		query listMovieScrapers {
			listMovieScrapers {
			  id
			  name
			  movie {
				supported_scrapes
			  }
			}
		  }
		"""
		ret = []
		result = self.__callGraphQL(query)
		for r in result["listMovieScrapers"]:
			if type in r["movie"]["supported_scrapes"]:
				ret.append(r["id"])
		return ret

	# Fragment Scrape
	def scrape_scene(self, scraper_id:int, scene):
		
		if not isinstance(scene, dict) or not scene.get("id"):
			log.warning('Unexpected Object passed to scrape_single_scene')
			log.warning(f'Type: {type(scene)}')
			log.warning(f'{scene}')

		query = """query ScrapeSingleScene($source: ScraperSourceInput!, $input: ScrapeSingleSceneInput!) {
			scrapeSingleScene(source: $source, input: $input) {
			  ...scrapedScene
			}
		  }
		"""
		
		variables = {
			"source": {
				"scraper_id": scraper_id
			},
			"input": {
				"query": None,
				"scene_id": scene["id"],
				"scene_input": {
					"title": scene["title"],
					"details": scene["details"],
					"url": scene["url"],
					"date": scene["date"],
					"remote_site_id": None
				}
			}
		}
		result = self.__callGraphQL(query, variables)
		if not result:
			return None
		scraped_scene_list = result["scrapeSingleScene"]
		if len(scraped_scene_list) == 0:
			return None
		else:
			return scraped_scene_list[0]
	def scrape_gallery(self, scraper_id:int, gallery):
		query = """query ScrapeGallery($scraper_id: ID!, $gallery: GalleryUpdateInput!) {
			scrapeGallery(scraper_id: $scraper_id, gallery: $gallery) {
			  ...scrapedGallery
			}
		  }
		"""
		variables = {
			"scraper_id": scraper_id,
			"gallery": {
				"id": gallery["id"],
				"title": gallery["title"],
				"url": gallery["url"],
				"date": gallery["date"],
				"details": gallery["details"],
				"rating": gallery["rating"],
				"scene_ids": [],
				"studio_id": None,
				"tag_ids": [],
				"performer_ids": [],
			}
		}

		result = self.__callGraphQL(query, variables)
		return result["scrapeGallery"]
	def scrape_performer(self, scraper_id:int, performer):
		query = """query ScrapePerformer($scraper_id: ID!, $performer: ScrapedPerformerInput!) {
			scrapePerformer(scraper_id: $scraper_id, performer: $performer) {
			  ...scrapedPerformer
			}
		  }
		"""
		variables = {
			"scraper_id": scraper_id,
			"performer": {
			"name": performer["name"],
			"gender": None,
			"url": performer["url"],
			"twitter": None,
			"instagram": None,
			"birthdate": None,
			"ethnicity": None,
			"country": None,
			"eye_color": None,
			"height": None,
			"measurements": None,
			"fake_tits": None,
			"career_length": None,
			"tattoos": None,
			"piercings": None,
			"aliases": None,
			"tags": None,
			"image": None,
			"details": None,
			"death_date": None,
			"hair_color": None,
			"weight": None,
		}
		}
		result = self.__callGraphQL(query, variables)
		return result["scrapePerformer"]

	# URL Scrape
	def scrape_scene_url(self, url):
		query = """
			query($url: String!) {
				scrapeSceneURL(url: $url) {
					...scrapedScene
				}
			}
		"""
		variables = { 'url': url }
		scraped_scene = self.__callGraphQL(query, variables)['scrapeSceneURL']

		if not scraped_scene:
			return None

		performers = []
		if scraped_scene["performers"]:
			for p in scraped_scene['performers']:
				p_match = self.find_performer(p)
				if p_match:
					performers.append({
						"stored_id": p_match["id"],
						"name": p_match["name"],
					})
				else:
					performers.append(p)
		scraped_scene['performers'] = performers
		return scraped_scene
	def scrape_movie_url(self, url):
		query = """
			query($url: String!) {
				scrapeMovieURL(url: $url) {
					...scrapedMovie
				}
			}
		"""
		variables = { 'url': url }
		result = self.__callGraphQL(query, variables)

		return result['scrapeMovieURL']
	def scrape_gallery_url(self, url):
		query = """
			query($url: String!) {
				scrapeGalleryURL(url: $url) {
					...scrapedGallery 
				}
			}
		"""
		variables = { 'url': url }
		result = self.__callGraphQL(query, variables)
		return result['scrapeGalleryURL']        
	def scrape_performer_url(self, url):
		query = """
			query($url: String!) {
				scrapePerformerURL(url: $url) {
					...scrapedPerformer
				}
			}
		"""
		variables = { 'url': url }
		result = self.__callGraphQL(query, variables)
		return result['scrapePerformerURL']

	# Stash Box
	def stashbox_scene_scraper(self, scene_ids, stashbox_index:int=0):
		query = """
			query QueryStashBoxScene($input: StashBoxSceneQueryInput!) {
				queryStashBoxScene(input: $input) {
					...scrapedScene
				}
			}
		"""
		variables = {
			"input": {
				"scene_ids": scene_ids,
				"stash_box_index": stashbox_index
			}
		}

		result = self.__callGraphQL(query, variables)

		return result["queryStashBoxScene"]
	def stashbox_submit_scene_fingerprints(self, scene_ids, stashbox_index:int=0):
		query = """
			mutation SubmitStashBoxFingerprints($input: StashBoxFingerprintSubmissionInput!) {
				submitStashBoxFingerprints(input: $input)
			}
		"""
		variables = {
			"input": {
				"scene_ids": scene_ids,
				"stash_box_index": stashbox_index
			}
		}

		result = self.__callGraphQL(query, variables)
		return result['submitStashBoxFingerprints']


	def find_duplacate_scenes(self, distance: PhashDistance=PhashDistance.EXACT):
		query = """
			query FindDuplicateScenes($distance: Int) {
				  findDuplicateScenes(distance: $distance) {
					...SlimSceneData
					__typename
				  }
			}
			fragment SlimSceneData on Scene {
				id
				title
				path
				oshash
				phash
				file {
				size
				duration
				video_codec
				width
				height
				framerate
				bitrate
				__typename
				}
				__typename
			}
		"""

		variables = { "distance": distance }
		result = self.__callGraphQL(query, variables)
		return result['findDuplicateScenes']
