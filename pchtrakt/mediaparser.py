# -*- coding: utf-8 -*-
# Authors: Jonathan Lauwers / Frederic Haumont
# URL: http://github.com/pchtrakt/pchtrakt
#
# This file is part of pchtrakt.
#
# pchtrakt is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pchtrakt is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pchtrakt.  If not, see <http://www.gnu.org/licenses/>.

#from os.path import basename, isfile
from urllib import quote_plus
from urllib2 import urlopen, HTTPError, URLError, Request
import json, re
from lib import parser
from movieparser import *
from lib.tvdb_api import tvdb_exceptions
from pchtrakt.config import *
from lib.tvdb_api import tvdb_api,tvdb_exceptions
from lib.utilities import Debug
from xml.etree import ElementTree

tvdb = tvdb_api.Tvdb()

class MediaParserResult():
    def __init__(self,file_name):
        self.file_name = file_name

class MediaParserResultTVShow(MediaParserResult):
    def __init__(self,file_name,name,season_number,episode_numbers,air_by_date):
        self.file_name = file_name
        self.name = name
        self.air_by_date = air_by_date
        #np = parser.NameParser()
        #parse_result = np.parse(self.file_name)
        if self.air_by_date:
            if self.name in cacheSerie.dictSerie:
                self.id = cacheSerie.dictSerie[self.name]['TvDbId']
            else:
                self.id = tvdb[self.name]['id']
            season_number = -1
            episode_numbers = [self.air_by_date]
            url = ('http://thetvdb.com/api/GetEpisodeByAirDate.php?apikey=0629B785CE550C8D&seriesid={0}&airdate={1}'.format(quote_plus(self.id), self.air_by_date))
            Debug('[The TvDB] GET EPISODE USING: ' + url)
            oResponse = ElementTree.parse(urlopen(url,None,5))
            #feed = RSSWrapper(tree.getroot())
            for movie in oResponse.findall('./'):
                #Debug("movie", repr(movie.title), movie.link)
                season_number = movie.find('SeasonNumber').text
                episode_numbers = movie.find('EpisodeNumber').text
        self.season_number = season_number
        self.episode_numbers = episode_numbers
        if self.name in cacheSerie.dictSerie:
            self.id = cacheSerie.dictSerie[self.name]['TvDbId']
            self.year = cacheSerie.dictSerie[self.name]['Year']
        else:
            try:
                self.id = tvdb[self.name]['id']
                pchtrakt.online = 1
                if tvdb[self.name]['firstaired'] != None:
                    self.year = tvdb[self.name]['firstaired'].split('-')[0]
                else:
                    self.year = None
                cacheSerie.dictSerie[self.name]={'Year':self.year,
                                                            'TvDbId':self.id}

                with open('cache.json','w') as f:
                    json.dump(cacheSerie.dictSerie, f, separators=(',',':'), indent=4)
            except tvdb_exceptions.tvdb_error, e:
                pchtrakt.online = 0

class MediaParserResultMovie(MediaParserResult):
    def __init__(self,file_name,name,year,imdbid):
        self.file_name = file_name#check if needed all below
        self.name = name
        self.year = year
        self.id = imdbid
        if pchtrakt.online and self.id == None:
            ImdbAPIurl = ('http://www.imdbapi.com/?t={0}&y={1}'.format(quote_plus(self.name.encode('utf-8', 'replace')), self.year))
            Debug('[IMDB api] Trying search 1: ' + ImdbAPIurl)
            try:
                oResponse = urlopen(ImdbAPIurl,None,5)
                #if json.load(foResponse['0']['Error'] == 'Movie not found!':
                #    print 'hello'
                myMovieJson = json.loads(oResponse.read())
                if myMovieJson['Response'] == "True":#in myMovieJson.keys():
                    #print "added "+myMovieJson["Title"]
                    self.id = myMovieJson['imdbID']
                    Debug('[IMDB api] Movie match using: ' + ImdbAPIurl)
                else:
                    ImdbAPIurl = ('http://www.deanclatworthy.com/imdb/?q={0}&year={1}'.format(quote_plus(self.name.encode('utf-8', 'replace')), self.year))
                    Debug('[IMDB api] Trying search 2: ' + ImdbAPIurl)
                    oResponse = urlopen(ImdbAPIurl,None,5)
                    myMovieJson = json.loads(oResponse.read())
                    if "title" in myMovieJson.keys():
                        self.id = myMovieJson['imdbid']
                        Debug('[IMDB api] Found Movie match using: ' + ImdbAPIurl)
                    else:
                        ImdbAPIurl = ('http://www.google.com/search?q=www.imdb.com:site+{0}+({1})&num=1&start=0'.format(quote_plus(self.name.encode('utf-8', 'replace')), self.year))
                        Debug('[IMDB api] Trying search 3: ' + ImdbAPIurl)
                        request = Request(ImdbAPIurl, None, {'User-Agent':'Mosilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11'})
                        urlfile = urlopen(request)
                        page = urlfile.read()
                        entries = re.findall("/title/tt(\d{7})/", page)
                        self.id = "tt"+str(entries[0])
                        Debug('[IMDB api] Search address = ' + ImdbAPIurl + ' ID = ' + self.id)
            except:
                raise MovieResultNotFound(file_name)
        #else:
        #    self.id = '0'

class MediaParserResultMoviebackup(MediaParserResult):
    def __init__(self,file_name,name,year,imdbid):
        self.file_name = file_name#check if needed all below
        self.name = name
        if year == None:
            self.year = ""
        else:
            self.year = year
        if pchtrakt.online:
            ImdbAPIurl = ('http://www.imdbapi.com/?t={0}&y={1}'.format(quote_plus(self.name.encode('utf-8', 'replace')), self.year))
            Debug('[IMDB api] Trying search 1: ' + ImdbAPIurl)
            try:
                oResponse = urlopen(ImdbAPIurl,None,5)
                myMovieJson = json.loads(oResponse.read())
                self.id = myMovieJson['imdbID']
                Debug('[IMDB api] Movie match using: ' + ImdbAPIurl)
            except URLError, HTTPError:
                pass
            except KeyError:
                ImdbAPIurl = ('http://www.deanclatworthy.com/imdb/?q={0}&year={1}'.format(quote_plus(self.name.encode('utf-8', 'replace')), self.year))
                Debug('[IMDB api] Trying search 2: ' + ImdbAPIurl)
                try:
                    oResponse = urlopen(ImdbAPIurl,None,5)
                    myMovieJson = json.loads(oResponse.read())
                    self.id = myMovieJson['imdbid']
                    Debug('[IMDB api] Found Movie match using: ' + ImdbAPIurl)
                except:
                    try:
                        address = ('http://www.google.com/search?q=www.imdb.com:site+{0}&num=1&start=0'.format(quote_plus(self.name.encode('utf-8', 'replace'))))
                        Debug('[IMDB api] Trying search 3: ' + address)
                        request = Request(address, None, {'User-Agent':'Mosilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11'})
                        urlfile = urlopen(request)
                        page = urlfile.read()
                        entries = re.findall("/title/tt(\d{7})/", page)
                        self.id = "tt"+str(entries[0])
                        Debug('[IMDB api] Search address = ' + address + ' ID = ' + self.id)
                    except:
                        raise MovieResultNotFound(file_name)
        else:
            self.id = '0'

class MediaParserUnableToParse(Exception):
    def __init__(self, file_name):
        self.file_name = file_name

class MediaParser():
    def __init__(self):
        self.TVShowParser = parser.NameParser()
        self.MovieParser = MovieParser()

    def parse(self, file_name):
        try:
            parsedResult = self.TVShowParser.parse(file_name)
            oResultTVShow = MediaParserResultTVShow(file_name,parsedResult.series_name,parsedResult.season_number,parsedResult.episode_numbers,parsedResult.air_by_date)
            return oResultTVShow
        except parser.InvalidNameException as e:
            oMovie = self.MovieParser.parse(file_name)
            return oMovie
        raise MediaParserUnableToParse(' [Pchtrakt] Unable to parse the filename and detecte an movie or a tv show')