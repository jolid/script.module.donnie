import urllib2, urllib, sys, os, re, random, copy
import htmlcleaner
import httplib2
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
import xbmc,xbmcplugin,xbmcgui,xbmcaddon
from t0mm0.common.net import Net
from t0mm0.common.addon import Addon
from scrapers import CommonScraper
net = Net()

class OneChannelServiceSracper(CommonScraper):
	def __init__(self, settingsid, DB=None, REG=None):
		if DB:
			self.DB=DB
		if REG:
			self.REG=REG
		self.addon_id = 'script.module.donnie'
		self.service='1channel'
		self.name = '1channel.ch'
		self.raiseError = False
		self.referrer = 'http://www.letmewatchthis.ch/'
		self.base_url = 'http://www.letmewatchthis.ch/'
		self.user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3'
		self.provides = []
		self._episodes = []
		self.AZ = ['1', 'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y', 'Z']
		self.settingsid = settingsid
		self.LOGGING_LEVEL = '0'
		self._loadsettings()
		self.settings_addon = self.addon


	def _getShows(self, silent=False):
		self.log("Getting All shows for %s", self.service)
		pDialog = xbmcgui.DialogProgress()
		if not silent:
			pDialog.create('Downloading shows from ' + self.service)
			pDialog.update(0, self.service, '')
		uri = 'index.php?tv=&sort=release'
		pagedata = self.getURL(uri, append_base_url=True)		
		if pagedata=='':
			return
		soup = BeautifulSoup(pagedata)
		div = soup.find('div', {'class': 'pagination'})
		links = div.findAll('a')
		a = links[len(links)-1]
		pages = re.search('&page=(.+?)$', a['href']).group(1)
		row = self.DB.query("SELECT current, full FROM rw_update_status WHERE identifier='tvshows' AND provider=?", [self.service])
		if len(row) > 0:
			offset = int(pages) - int(row[1])		
			current = int(row[0]) + offset - 1
		else:
			current = pages

		for page in reversed(range(1,int(current)+1)):
			percent = int((100 * (int(pages) - page))/int(pages))
			if not self._getShowsByPg(str(page), pages, pDialog, percent, silent):
				break
			if not silent:
				if (pDialog.iscanceled()):
					print 'Canceled download'
					return

		if not silent:		
			pDialog.close()
		self.DB.commit()
		self.update_cache_status("tvshows")
		self.log('Dowload complete!', level=0)
	

	def _getShowsByPg(self, page, pages, pDialog, percent, silent):
		self.log("getting TV Shows by %s", page)
		uri = 'index.php?tv=&sort=release&page=%s' % page
		pagedata = self.getURL(uri, append_base_url=True)
		if pagedata=='':
			return False
		soup = BeautifulSoup(pagedata)
		shows = soup.findAll('div', {'class' : 'index_item index_item_ie'})
		findYear = re.compile('\((\d{4})\)$')
		for show in shows:
			
			try:
				a = show.find('a')
				href = a['href']
				name = a['title']
				name = name[6:len(name)]
				character = self.getInitialChr(name)
				year = findYear.search(name).group(1)
				genres = []
				genre_temp = show.find('div', {'class' : 'item_categories'})
				if genre_temp:
					genre_links = genre_temp.findAll('a')
					for genre in genre_links:
						genres.append(str(genre.string))
				self.addShowToDB(name, href, character, year, genres)
				if not silent:
					pDialog.update(percent, self.service + ' page: ' + str(page), name)
			except:
				pass
			
		if page == 1:
			self.DB.execute("DELETE FROM rw_update_status WHERE provider=? and identifier=?", [self.service, 'tvshows'])
		else:		
			self.DB.execute("REPLACE INTO rw_update_status(provider, identifier, current, full) VALUES(?, ?, ?, ?)", [self.service, 'tvshows', page, pages])
		self.DB.commit()
		return True


	def _getNewEpisodes(self, silent=False):
		self.log("Getting new episodes for %s", self.service)
		episodes = []
		pagedata = self.getURL('?tv', append_base_url=True)
		if pagedata=='':
			return False
		
		soup = BeautifulSoup(pagedata)
		div = soup.findAll('div', {'id':'slide-runner'})[0]
		links = div.findAll('a')

		for link in links:
			title = re.sub(r'Season (\d+?) Episode (\d+?)',  r'\1x\2', link['title'])
			title = title[6:len(title)]
			episode = [self.service, title, link['href']]
			episodes.append(episode)
		return episodes

	def _getEpisodes(self, showid, show, url, pDialog, percent, silent, createFiles=True):
		self.log("Getting episodes for %s", show)
		pagedata = self.getURL(url, append_base_url=True)
		if pagedata=='':
			return False
		soup = BeautifulSoup(pagedata)
	
		divs = soup.findAll("div", {"class" : "tv_episode_item"})
		for div in divs:
			a = div.find('a')
			href = a['href']
			season = re.search('season-(\d)+', href).group(0)
			season = season.replace('season-', '')
			episode = re.search('episode-(\d)+', href).group(0)
			episode = episode.replace('episode-', '').zfill(2)
			try:
				name = a.find('span').string
				name = name[2:len(name)]
			except:
				name = " Episode " + episode
			if not silent:
				display = "%sx%s %s" % (season, episode, name)
				pDialog.update(percent, show, display)
			self.addEpisodeToDB(showid, show, name, season, episode, self.base_url + href, createFiles=createFiles)
		self.DB.commit()
		return True

	def _getMovies(self, silent=False):
		print "Getting recent movies for: " + self.service
		pDialog = xbmcgui.DialogProgress()
		uri = '/index.php?sort=release'
		if not silent:
			pDialog.create('Caching recent movies from ' + self.service)
			pDialog.update(0, self.service, '')
		pagedata = self.getURL(uri, append_base_url=True)		
		if pagedata=='':
			return
		soup = BeautifulSoup(pagedata)
		div = soup.find('div', {'class': 'pagination'})
		links = div.findAll('a')
		a = links[len(links)-1]
		pages = re.search('&page=(.+?)$', a['href']).group(1)
		row = self.DB.query("SELECT current, full FROM rw_update_status WHERE identifier='movies' AND provider=?", [self.service])
		if len(row) > 0:
			offset = int(pages) - int(row[1])		
			current = int(row[0]) + offset - 1
		else:
			current = pages

		for page in reversed(range(1,int(current)+1)):
			percent = int((100 * (int(pages) - page))/int(pages))
			if not self._getMoviesByPg(page, pages, pDialog, percent, silent):
				break
			if not silent:
				if (pDialog.iscanceled()):
					print 'Canceled download'
					return

		if not silent:		
			pDialog.close()
		self.DB.commit()
		self.update_cache_status("movies")
		self.log('Dowload complete!', level=0)


	def _getMoviesByPg(self, page, pages, pDialog, percent, silent):
		uri = '/index.php?sort=release&page=' + str(page)
		pagedata = self.getURL(uri, append_base_url=True)		
		if pagedata=='':
			return
		soup = BeautifulSoup(pagedata)
		divs = soup.findAll("div", {"class" : "index_item index_item_ie"})
		for div in divs:
			try:
				a = div.find('a', { "href" : re.compile(r"^/watch-") })
				href = a['href']
				title = a['title']
				title = title[6:len(title)]
				year = re.search('\((.+?)\)$', title)
				if year:
					year = year.group(1)
				else:
					year = '0000'
				character = self.getInitialChr(title)
				imdb = re.search('^/watch-\d{1,10}', href).group(0)
				genres = []
				genre_temp = div.find('div', {'class' : 'item_categories'})
				if genre_temp:
					genre_links = genre_temp.findAll('a')
					for genre in genre_links:
						genres.append(str(genre.string))
				self.addMovieToDB(title, href, self.service + '://' + href, character, year, genres)
				if not silent:
					pDialog.update(percent, self.service + ': page ' + str(page), title)
			except Exception, e:
				print '******HTTP ERROR: %s' % e
				pass
		if page == 1:
			self.DB.execute("DELETE FROM rw_update_status WHERE provider=? and identifier=?", [self.service, 'movies'])
		else:		
			self.DB.execute("REPLACE INTO rw_update_status(provider, identifier, current, full) VALUES(?, ?, ?, ?)", [self.service, 'movies', page, pages])
		self.DB.commit()
		return True


	def _getStreams(self, episodeid=None, movieid=None, directurl=None):
		streams = []
		if directurl:
			self.getProviders()
			url = directurl
		else:
			url = self.getServices(episodeid=episodeid, movieid=movieid)

		if not url:
			return streams
		if self.ENABLE_MIRROR_CACHING:
			if url:
				self.log(url)
				cache_url = url
			else:
				return 	streams		
			cached = self.checkStreamCache(cache_url)
			if len(cached) > 0:
				self.log("Loading streams from cache")
				for temp in cached:
					self.getStreamByPriority(temp[0], temp[1])
				return cached

		self.log("Locating streams for provided by service: %s", self.service)
		if episodeid:
			pagedata = self.getURL(url, append_base_url=False)
		else:
			pagedata = self.getURL(url, append_base_url=True)	
		if pagedata=='':
			return
		#print pagedata
		soup = BeautifulSoup(pagedata)
		spans = soup.findAll('span', {'class' : 'movie_version_link'})
		for span in spans:		
			a = span.find('a', { "href" : re.compile(r"^/external.php") })
			if a:
				tr = span.parent.parent
				host = tr.find('span', { 'class' : 'version_host' })
				host = host.find('script').string
				host = host[18:len(host)-3]
				if self.checkProviders(host):
					try:
						views = tr.find('span', { 'class' : 'version_veiws' })
						views = views.string
						host = host + ' ('+views+')'
					except:
						pass				
					frame_url = a['href']
					raw_url = frame_url
					if raw_url:
						#streams.append(['1Channel - ' + host, self.service + '://' + raw_url])
						self.getStreamByPriority('1Channel - ' + host, self.service + '://' + raw_url)
						if self.ENABLE_MIRROR_CACHING:
							self.cacheStreamLink(cache_url, '1Channel - ' + host, self.service + '://' + raw_url)	
						

		self.DB.commit()
		#self.log(streams)
		#return streams

	def sortStreams(self, random):
		if self.getBoolSetting('enable-autorank'):

			streams = reversed(sorted(random,  key=lambda s: int(re.search('\((.+?) views', s[0]).group(1))))
		else:
			streams = sorted(random,  key=lambda s: s[0])
		return streams

	def _resolveStream(self, stream):
		import urlresolver
		raw_url = stream.replace(self.service + '://', '')
		resolved_url = ''
		'''framedata = self.getURL(raw_url, append_base_url=True)
		if not framedata:
			return None
		soup = BeautifulSoup(framedata)
		print soup
		raw_url = soup.find('noframes')
		if raw_url:
			raw_url = raw_url.string
		else:
			frame = soup.find('iframe')
			print frame
			source = frame['src']
			raw_url = re.search('file=(.+?)&subid=', source).group(0)
			raw_url = urllib.unquote(raw_url[5:len(raw_url)-7])
			print raw_url
		try:
			resolved_url = urlresolver.HostedMediaFile(url=raw_url).resolve()
		except:
			pass'''
		try:
			raw_url = self.base_url + raw_url
			h = httplib2.Http()
			h.follow_redirects = False
			(response, body) = h.request(raw_url)
			resolved_url = urlresolver.HostedMediaFile(url=response['location']).resolve()
		except:
			print raw_url
			framedata = self.getURL(raw_url, append_base_url=False)
			if not framedata:
				return None
			soup = BeautifulSoup(framedata)
			raw_url = soup.find('noframes')
			if raw_url:
				raw_url = raw_url.string
				resolved_url = urlresolver.HostedMediaFile(url=raw_url).resolve()

		if not resolved_url:
			resolved_url = self.resolveLink(raw_url)
			if not resolved_url:
				self.log("Unable to resolve url, sorry!", level=0)
				return None
		#self.logHost(self.service, raw_url)
		return resolved_url

	def _getServicePriority(self, link):
		self.log(link)
		host = re.search('- (.+?) \(', link).group(1)
		row = self.DB.query("SELECT priority FROM rw_providers WHERE mirror=? and provider=?", [host, self.service])
		return row[0]

	def getStreamByPriority(self, link, stream):
		self.log(link)
		host = re.search('- (.+?) \(', link).group(1)	
		'''SQL = 	"INSERT INTO rw_stream_list(stream, url, priority) " \
			"SELECT ?, ?, priority " \
			"FROM rw_providers " \
			"WHERE mirror=? and provider=?"
		self.DB.execute(SQL, [link, stream, host, self.service])'''
		
		SQL = 	"INSERT INTO rw_stream_list(stream, url, priority, machineid) " \
		"SELECT ?, ?, priority, ? " \
		"FROM rw_providers " \
		"WHERE mirror=? and provider=?"
		self.DB.execute(SQL, [link, stream, self.REG.getSetting('machine-id'), host, self.service])
	
	def resolveLink(self, link):
		resolved_url = None
		self.log("Attempting local resolver")
		link_type = self.whichProviderType(link)

		if link_type == 'MR':
			resolved_url = IcefilmsServiceSracper().resolve_movreel(link)
			self.log("Movreel retruned: %s", resolved_url)
			return resolved_url
		return resolved_url
		
	
	def whichProviderType(self, link):
		link_type = ''
                ismovreel = re.search('movreel\.com', str(link))
                
		if ismovreel:
                	link_type = 'MR'
		return link_type

	def _resolveIMDB(self, uri):
		imdb = ''
		pagedata = self.getURL(uri, append_base_url=True)		
		if pagedata=='':
			return
		soup = BeautifulSoup(pagedata)
		div = soup.find('div', {'class' : 'mlink_imdb'})
		a=div.find('a')
		imdb = a['href']
		imdb = imdb.replace('http://www.imdb.com/title/', '')
		return self.padIMDB(imdb)
