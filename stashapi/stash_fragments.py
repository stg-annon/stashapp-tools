
GQL_FRAGMENTS = {
	"scrapedScene":"""
		fragment scrapedScene on ScrapedScene {
		  title
		  details
		  url
		  date
		  image
		  studio{
			...scrapedStudio
		  }
		  tags{
			...scrapedTag
		  }
		  performers{
			...scrapedPerformer
		  }
		  movies{
			...scrapedMovie
		  }
		  duration
		  __typename
		}
	""",
	"scrapedGallery":"""
		fragment scrapedGallery on ScrapedGallery {
		  title
		  details
		  url
		  date
		  studio{
			...scrapedStudio
		  }
		  tags{ ...scrapedTag }
		  performers{
			...scrapedPerformer
		  }
		  __typename
		}
	""",
	"scrapedPerformer":"""
		fragment scrapedPerformer on ScrapedPerformer {
		  stored_id
		  name
		  gender
		  url
		  twitter
		  instagram
		  birthdate
		  ethnicity
		  country
		  eye_color
		  height
		  measurements
		  fake_tits
		  career_length
		  tattoos
		  piercings
		  aliases
		  tags { ...scrapedTag }
		  images
		  details
		  death_date
		  hair_color
		  weight
		  remote_site_id
		  __typename
		}
	""",
	"scrapedTag": """
		fragment scrapedTag on ScrapedTag {
			stored_id
			name
			__typename
		}
	""",
	"scrapedMovie": """
		fragment scrapedMovie on ScrapedMovie {
			stored_id
			name
			aliases
			duration
			date
			rating
			director
			synopsis
			url
			studio {
				...scrapedStudio
			}
			front_image
			back_image
			__typename
		}
	""",
	"scrapedStudio": """
		fragment scrapedStudio on ScrapedStudio {
			stored_id
			name
			url
			remote_site_id
			__typename
		}
	""",
	"stashSceneUpdate":"""
		fragment stashSceneExit on Scene {
			id
			title
			details
			url
			date
			rating
			gallery_ids
			studio_id
			performer_ids
			movies
			tag_ids
			stash_ids
			__typename
		}
	""",
	"stashScene":"""
		fragment stashScene on Scene {
		  id
		  checksum
		  oshash
		  phash
		  title
		  details
		  url
		  date
		  rating
		  organized
		  o_counter
		  path
		  tags {
			...stashTag
		  }
		  file {
			size
			duration
			video_codec
			audio_codec
			width
			height
			framerate
			bitrate
			__typename
		  }
		  galleries {
			id
			checksum
			path
			title
			url
			date
			details
			rating
			organized
			studio {
			  id
			  name
			  url
			  __typename
			}
			image_count
			tags {
			  ...stashTag
			}
		  }
		  performers {
			...stashPerformer
		  }
		  scene_markers { 
			...stashSceneMarker
		  }
		  studio{
			...stashStudio
		  }
		  stash_ids{
			endpoint
			stash_id
			__typename
		  }
		  __typename
		}
	""",
	"stashGallery":"""
		fragment stashGallery on Gallery {
			id
			checksum
			path
			title
			date
			url
			details
			rating
			organized
			image_count
			cover {
				paths {
					thumbnail
				}
			}
			studio {
				id
				name
				__typename
			}
			tags {
				...stashTag
			}
			performers {
				...stashPerformer
			}
			scenes {
				id
				title
				__typename
			}
			images {
				id
				title
			}
			__typename
		}
	""",
	"stashPerformer":"""
		fragment stashPerformer on Performer {
			id
			checksum
			name
			url
			gender
			twitter
			instagram
			birthdate
			ethnicity
			country
			eye_color
			height
			measurements
			fake_tits
			career_length
			tattoos
			piercings
			aliases
			favorite
			tags { ...stashTag }
			image_path
			scene_count
			image_count
			gallery_count
			stash_ids {
				stash_id
				endpoint
				__typename
			}
			rating
			details
			death_date
			hair_color
			weight
			__typename
		}
	""",
	"stashSceneMarker":"""
		fragment stashSceneMarker on SceneMarker {
			id
			scene { id }
			title
			seconds
			primary_tag { ...stashTag }
			tags { ...stashTag }
			__typename
		}
	""",
	"stashMovie":"""
		fragment stashMovie on Movie {
			id
			name
			aliases
			duration
			date
			rating
			studio { id }
			director
			synopsis
			url
			created_at
			updated_at
			scene_count
			__typename
		}
	""",
	"stashTag":"""
		fragment stashTag on Tag {
			id
			name
			aliases
			image_path
			scene_count
			__typename
		}
	""",
	"stashStudio":"""
		fragment stashStudio on Studio {
			id
			name
			url
			aliases
			rating
			details
			stash_ids{
				endpoint
				stash_id
				__typename
			}
			parent_studio {
				id
				name
			}
			__typename
		}
	""",
	"ConfigData":"""
		fragment ConfigData on ConfigResult {
			general {
				...ConfigGeneralData
			}
			interface {
				...ConfigInterfaceData
			}
			dlna {
				...ConfigDLNAData
			}
		}
	""",
	"ConfigGeneralData":"""
		fragment ConfigGeneralData on ConfigGeneralResult {
			stashes {
				path
				excludeVideo
				excludeImage
			}
			databasePath
			generatedPath
			configFilePath
			cachePath
			calculateMD5
			videoFileNamingAlgorithm
			parallelTasks
			previewAudio
			previewSegments
			previewSegmentDuration
			previewExcludeStart
			previewExcludeEnd
			previewPreset
			maxTranscodeSize
			maxStreamingTranscodeSize
			apiKey
			username
			password
			maxSessionAge
			logFile
			logOut
			logLevel
			logAccess
			createGalleriesFromFolders
			videoExtensions
			imageExtensions
			galleryExtensions
			excludes
			imageExcludes
			scraperUserAgent
			scraperCertCheck
			scraperCDPPath
			stashBoxes {
				name
				endpoint
				api_key
			}
		}
	""",
	"ConfigInterfaceData":"""
		fragment ConfigInterfaceData on ConfigInterfaceResult {
			menuItems
			soundOnPreview
			wallShowTitle
			wallPlayback
			maximumLoopDuration
			autostartVideo
			showStudioAsText
			css
			cssEnabled
			language
			slideshowDelay
			handyKey
		}
	""",
	"ConfigDLNAData":"""
		fragment ConfigDLNAData on ConfigDLNAResult {
			serverName
			enabled
			whitelistedIPs
			interfaces
		}
	""",
}