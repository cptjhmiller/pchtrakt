from sys import version_info
from os.path import isfile, isdir
from os import listdir
from os import rename
from xml.etree import ElementTree
from lib import utilities
from lib.utilities import Debug
from urllib import unquote_plus
from pchtrakt.exception import BetaSerieAuthenticationException
from pchtrakt import mediaparser as mp
from pchtrakt import betaseries as bs
from pchtrakt.config import *
from time import sleep, time
import pchtrakt
import glob

class OutToMainLoop(Exception):
    pass

def insensitive_glob(pattern):
    def either(c):
        return '[%s%s]'%(c.lower(),c.upper()) if c.isalpha() else c
    return ''.join(map(either,pattern))

def Oversightwatched(searchValue):
    if isfile("/share/Apps/oversight/index.db"):
        newfile = ""
        pchtrakt.logger.info('[Oversight] Doing update...')
        addValue = "\t_w\t1\t"
        replacevalue = "\t_w\t0\t"
        file = open("/share/Apps/oversight/index.db", "r")
        for line in file:
            line = line.decode('utf8', 'replace')
            if searchValue in line:
                if replacevalue in line:
                    line = line.replace(replacevalue, addValue)
                    pchtrakt.logger.info('[Oversight] Updating ' + searchValue)
                elif not addValue in line:
                    line = line.replace(searchValue+"	", searchValue+addValue)
                    pchtrakt.logger.info('[Oversight] Updating ' + searchValue)
                else:
                    pchtrakt.logger.info('[Oversight] ' + searchValue + ' was already marked')
            newfile = newfile + line.encode('utf8', 'replace')
        file.close()
        file = open("/share/Apps/oversight/index.db", "w")
        file.write(newfile)
        file.close()
        newfile = ""
    else:
        pchtrakt.logger.info('[Oversight] Could not find your Oversight database file.')

def scrobbleMissed():
    ctime = time()
    pchtrakt.missed = {}
    if isfile('missed.scrobbles'):
        with open('missed.scrobbles','r+') as f:
            pchtrakt.missed = json.load(f)
    pchtrakt.missed[pchtrakt.lastPath]={"Totaltime": int(pchtrakt.Ttime), "Totallength": int(ctime)}
    with open('missed.scrobbles','w') as f:
        json.dump(pchtrakt.missed, f, separators=(',',':'), indent=4)

def repl_func(m):
    return m.group(1) + m.group(2).upper()

def showStarted(myMedia):
    if TraktScrobbleTvShow:
        percent = myMedia.oStatus.percent * len(myMedia.parsedInfo.episode_numbers) - (myMedia.idxEpisode * 100 )#fixed percent for multipleEpisode
        if percent < 0:
            percent = 0
        if str(myMedia.parsedInfo.season_number) == "None":
            myMedia.parsedInfo.season_number = "1"
        response = utilities.watchingEpisodeOnTrakt(myMedia.parsedInfo.id,
                                                        str(myMedia.parsedInfo.season_number),
                                                        str(myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode]),
                                                        str(percent))
        if response and ('action' in response and response['action'] == 'start'):
            msg = ' [traktAPI] Started watching %s Season %d Episode %d' % (response['show']['title'], response['episode']['season'], response['episode']['number'])
        else:
            msg = ' [traktAPI] No response from Trakt.tv'
        pchtrakt.logger.info(msg)

def movieStarted(myMedia):
    response = utilities.watchingMovieOnTrakt(myMedia.parsedInfo.id,
												str(myMedia.oStatus.percent))
    if response and ('action' in response and response['action'] == 'start'):
        msg = ' [traktAPI] Started watching %s' % (response['movie']['title'])
    else:
        msg = ' [traktAPI] No response from Trakt.tv'
    pchtrakt.logger.info(msg)

def showStopped(myMedia):
    response = utilities.cancelWatchingEpisodeOnTrakt(myMedia)
    if response:
        msg = ' [traktAPI] Tv Show has stopped: - %s' %(response)
    else:
        msg = ' [traktAPI] No response from Trakt.tv'
    pchtrakt.logger.info(msg)

def movieStopped(myMedia):
    response = utilities.cancelWatchingMovieOnTrakt(myMedia)
    if response:
        msg = ' [traktAPI] Movie has stopped: %s' %(response)
    else:
        msg = ' [traktAPI] No response from Trakt.tv'
    pchtrakt.logger.info(msg)

def videoStopped(myMedia):
    if not pchtrakt.isTvShow and not pchtrakt.isMovie:
        Debug("[Pchtrakt] ****NOT TV OR FILM****")
    if pchtrakt.isTvShow and TraktScrobbleTvShow:
        showStopped(myMedia)
    elif pchtrakt.isMovie and TraktScrobbleMovie:
        movieStopped(myMedia)
    if pchtrakt.CreatedFile == 1:
        if YamjPath != "/":
            UpdateXMLFiles(pchtrakt)
        if apiurl != "":
            utilities.watched(pchtrakt)
    if markOversight and pchtrakt.lastPercent > watched_percent:
        Oversightwatched(pchtrakt.lastName)
    if (TraktScrobbleTvShow or TraktScrobbleMovie) and (not pchtrakt.online and pchtrakt.watched):
        pchtrakt.logger.info(' [Pchtrakt] saving off-line scrobble')
        scrobbleMissed()

def showStillRunning(myMedia):
    showStarted(myMedia)

def movieStillRunning(myMedia):
    movieStarted(myMedia)

def showIsEnding(myMedia):
    if BetaSeriesScrobbleTvShow:
        result = 0
        msg = ' [BetaSAPI] Video is '
        serieXml = bs.getSerieUrl(myMedia.parsedInfo.id, myMedia.parsedInfo.name)
        if serieXml is not None:
            token = bs.getToken()
            isWatched = bs.isEpisodeWatched(serieXml,token,myMedia.parsedInfo.season_number,myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode])
            Debug('[BetaSAPI] Is episode watched: {0}'.format(isWatched))
            if not isWatched:
                result = bs.scrobbleEpisode(serieXml
                                                    ,token,
                                                    myMedia.parsedInfo.season_number,
                                                    myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode])
                bs.destroyToken(token)
                msg += 'ending: '
            else:
                bs.destroyToken(token)
                msg += 'already watched: '
            if result or isWatched:
                result = 1
                msg += u'{0} {1}x{2}'.format(myMedia.parsedInfo.name,
                                           myMedia.parsedInfo.season_number,
                                           myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode]
                                           )
                pchtrakt.logger.info(msg)

            else:
                result = 1
        else:
            msg += 'not found '
            pchtrakt.logger.info(msg)
            result = 1
    #if TraktScrobbleTvShow:
    #    Debug("[traktAPI] Tv Show is ending")
    #    result = 0
    #    if str(myMedia.parsedInfo.season_number) == "None":
    #        myMedia.parsedInfo.season_number = "1"
    #    try:
    #        Debug('NAME: ' + myMedia.parsedInfo.name + ' Season: ' + str(myMedia.parsedInfo.season_number) + ' Episode: ' + str(myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode]))
    #    except Exception as e:
    #        print e
    #    response = utilities.scrobbleEpisodeOnTrakt(myMedia.parsedInfo.id,
    #                                                myMedia.parsedInfo.name,
    #                                                myMedia.parsedInfo.year,
	#                                                str(myMedia.parsedInfo.season_number),
    #                                                str(myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode]),
    #                                                str(myMedia.oStatus.totalTime),
    #                                                str(myMedia.oStatus.percent))
    #    if response:
    #        msg = ' [traktAPI] Tv Show is ending: - %s ' %(response)
    #        pchtrakt.logger.info(msg)
    #        result = 1
    #else:
    #    result = 1
    if BetaSeriesScrobbleTvShow:
        return result
    else:
        return 1

def movieIsEnding(myMedia):#Delete
    #Debug("[traktAPI] Movie is ending")
    #response = utilities.scrobbleMovieOnTrakt(myMedia.parsedInfo.id,
    #                                           myMedia.parsedInfo.name,
    #                                           myMedia.parsedInfo.year,
    #                                           str(myMedia.oStatus.totalTime),
    #                                           str(myMedia.oStatus.percent))
    #if response:
    #    if 'message' in response:
    #        if response['message'] != 'fake scrobble':
    #            msg = ' [traktAPI] Movie is ending: %s' %(response)
    #            pchtrakt.logger.info(msg)
    #    return 1
    #return 0
    return 1

def movieIsSeen(myMedia, SeenTime):
    response = utilities.setMoviesSeenOnTrakt(myMedia.parsedInfo.id,
                                              myMedia.parsedInfo.name,
                                              myMedia.parsedInfo.year,
                                              myMedia.oStatus.percent,
                                              str(SeenTime))
    if 'action' in response:
        if response['action'] == 'scrobble':
            return 1
    return 0

def showIsSeen(myMedia, SeenTime):
    response = utilities.setEpisodesSeenOnTrakt(myMedia.parsedInfo.id,
                                                    myMedia.parsedInfo.name,
                                                    myMedia.parsedInfo.year,
													str(myMedia.parsedInfo.season_number),
                                                    str(myMedia.parsedInfo.episode_numbers[myMedia.idxEpisode]),
                                                    myMedia.oStatus.percent,
                                                    str(SeenTime))
    if 'action' in response:
        if response['action'] == 'scrobble':
            return 1
    return 0

def videoStatusHandleMovie(myMedia):
    if pchtrakt.lastPath != myMedia.oStatus.fullPath:
        pchtrakt.watched = 0
        pchtrakt.lastPath = myMedia.oStatus.fullPath
        pchtrakt.lastName = myMedia.oStatus.fileName
        pchtrakt.lastPercent = myMedia.oStatus.percent
        pchtrakt.currentTime = myMedia.oStatus.currentTime
        if TraktScrobbleMovie and pchtrakt.lastPath != '':
            movieStarted(myMedia)
    if pchtrakt.problem == '':
        if not pchtrakt.watched and TraktScrobbleMovie:
            if myMedia.oStatus.percent > watched_percent:
                pchtrakt.watched = movieIsEnding(myMedia)
                if pchtrakt.watched:
                    pchtrakt.StopTrying = 0
            #elif myMedia.oStatus.currentTime > pchtrakt.currentTime + int(TraktRefreshTime)*60:
            #    pchtrakt.currentTime = myMedia.oStatus.currentTime
            #    movieStillRunning(myMedia)
        elif myMedia.oStatus.percent < 10 and myMedia.oStatus.status != 'noplay' and TraktScrobbleMovie:
            pchtrakt.logger.info(' [Pchtrakt] It seems you came back at the begining of the video... so I say to trakt it\'s playing')
            pchtrakt.watched = 0
            pchtrakt.currentTime = myMedia.oStatus.currentTime
            movieStarted(myMedia)

def videoStatusHandleTVSeries(myMedia):
    if len(myMedia.parsedInfo.episode_numbers)>1:
            doubleEpisode = 1
    else:
        doubleEpisode = 0
    if pchtrakt.lastPath != myMedia.oStatus.fullPath:
        pchtrakt.watched = 0
        pchtrakt.lastShowName = myMedia.parsedInfo.name
        pchtrakt.lastPath = myMedia.oStatus.fullPath
        pchtrakt.lastName = myMedia.oStatus.fileName
        pchtrakt.lastPercent = myMedia.oStatus.percent
        pchtrakt.episode_numbers = myMedia.parsedInfo.episode_numbers 
        pchtrakt.season_number = myMedia.parsedInfo.season_number
        pchtrakt.currentTime = myMedia.oStatus.currentTime
        myMedia.idxEpisode = 0
        if pchtrakt.lastPath != '' and (TraktScrobbleTvShow or BetaSeriesScrobbleTvShow):
            if doubleEpisode:
                while myMedia.oStatus.percent > (myMedia.idxEpisode + 1) * watched_percent/len(myMedia.parsedInfo.episode_numbers):
                    myMedia.idxEpisode += 1
                showStarted(myMedia)
                pchtrakt.currentTime = myMedia.oStatus.currentTime
            else:
                showStarted(myMedia)
    if pchtrakt.problem == '':
        if not pchtrakt.watched and (TraktScrobbleTvShow or BetaSeriesScrobbleTvShow):
            if myMedia.oStatus.percent > watched_percent:
                pchtrakt.watched = showIsEnding(myMedia)
            #elif myMedia.oStatus.currentTime > pchtrakt.currentTime + int(TraktRefreshTime)*60:
            #    pchtrakt.currentTime = myMedia.oStatus.currentTime
            #    showStillRunning(myMedia)
            elif doubleEpisode and myMedia.oStatus.percent > (myMedia.idxEpisode+1) * watched_percent/len(myMedia.parsedInfo.episode_numbers) and myMedia.idxEpisode+1 < len(myMedia.parsedInfo.episode_numbers):
                showIsEnding(myMedia)
                myMedia.idxEpisode += 1
                showStarted(myMedia)
        elif myMedia.oStatus.percent < 10 and myMedia.oStatus.status != 'noplay' and (TraktScrobbleTvShow or BetaSeriesScrobbleTvShow):
            pchtrakt.logger.info(' [Pchtrakt] It seems you came back at the begining of the video... so I say to trakt it\'s playing')
            pchtrakt.watched = 0
            pchtrakt.currentTime = myMedia.oStatus.currentTime
            showStarted(myMedia)

def videoStatusHandle(myMedia):
    if isinstance(myMedia.parsedInfo,mp.MediaParserResultTVShow):
        pchtrakt.isTvShow = 1
        videoStatusHandleTVSeries(myMedia)
    elif isinstance(myMedia.parsedInfo,mp.MediaParserResultMovie):
        pchtrakt.isMovie = 1
        videoStatusHandleMovie(myMedia)
    else:
        pchtrakt.StopTrying = 1
    pchtrakt.lastPath = myMedia.oStatus.fullPath
    pchtrakt.lastName = myMedia.oStatus.fileName
    pchtrakt.lastPercent = myMedia.oStatus.percent

def isIgnored(myMedia):
    ignored = False
    ignored = isKeywordIgnored(myMedia.oStatus.fileName)
    if not ignored and ignored_repertory[0] != '':
        for el in myMedia.oStatus.fullPath.replace('/opt/sybhttpd/localhost.drives/', '').split('/'):
            Debug("[Pchtrakt] Checking if %s is an ignored folder" % el)
            if el in ignored_repertory:
                msg = ' [Pchtrakt] This video is in a ignored repertory: {0}'.format(el) + ' Waiting for next file to start.'
                pchtrakt.logger.info(msg)
                ignored = True
                break
    if not ignored and YamjIgnoredCategory[0] != '':
        if YamjPath != "/":
            #YAMJ2 Genre
            file = myMedia.oStatus.fileName.encode('utf-8', 'replace').rsplit('.',1)[0] + '.xml'
            oXml = ElementTree.parse(YamjPath + file)
            genres = oXml.findall('.//genre')
            ignored = isGenreIgnored(genres)
        elif apiurl != "":
            #YAMJ3 Genre
            genres = []
            genre = utilities.getgenres(myMedia.oStatus.fileName.encode('utf-8', 'replace'))
            x = 0
            while x != genre['count']:
                genres.append(genre['results'][x]['name'])
                x = x + 1
            ignored = isY3GenreIgnored(genres)
    return ignored

def isKeywordIgnored(title):
    if ignored_keywords[0] != '':
        for keyword in ignored_keywords:
            if keyword.lower() in title.lower():
                msg = ' [Pchtrakt] This file contains an ignored keyword. Waiting for next file to start.'
                pchtrakt.logger.info(msg)
                return True
    return False

def isGenreIgnored(genres):
    txt = ' [Pchtrakt] The ignored genres are :{0}'.format(YamjIgnoredCategory)
    pchtrakt.logger.info(txt)
    for genre in genres:
        genre = genre.text.strip().lower()
        txt = ' [Pchtrakt] This genre is {0}'.format(genre)
        txt += ' --- Should it be ignored? {0}'.format(genre in YamjIgnoredCategory)
        pchtrakt.logger.info(txt)
        if genre in YamjIgnoredCategory:
            txt = ' [Pchtrakt] This video is in the ignored genre {0}'.format(genre)
            pchtrakt.logger.info(txt)
            return True
    return False

def isY3GenreIgnored(genres):
    txt = ' [Pchtrakt] The ignored genres are :{0}'.format(YamjIgnoredCategory)
    pchtrakt.logger.info(txt)
    for genre in genres:
        genre = genre.strip().lower()
        txt = ' [Pchtrakt] This genre is {0}'.format(genre)
        txt += ' --- Should it be ignored? {0}'.format(genre in YamjIgnoredCategory)
        pchtrakt.logger.info(txt)
        if genre in YamjIgnoredCategory:
            txt = ' [Pchtrakt] This video is in the ignored genre {0}'.format(genre)
            pchtrakt.logger.info(txt)
            return True
    return False

def watchedFileCreation(myMedia):
    try:
        Debug('[Pchtrakt] watchedFileCreation')
        path = myMedia.oStatus.fileName.encode('utf-8', 'replace')
    except:
        Debug('doing except for path')
        path = myMedia.oStatus.fileName.encode('latin-1', 'replace')
    if YamJWatchedVithVideo:
        try:
            path = myMedia.oStatus.fullPath.encode('utf-8', 'replace')
        except:
            path = myMedia.oStatus.fullPath.encode('latin-1', 'replace')
        if (path.split(".")[-1] == "DVD"):#Remember that .DVD extension
            path = path[:-4]
        if not OnPCH:
            path = path.replace('/opt/sybhttpd/localhost.drives/','')
            path = path.split('/', 2)[2]
            path = '{0}{1}'.format(YamjWatchedPath, path)
    else:
        if (path.split(".")[-1] == "DVD"):
            path = path[:-4]
        path = '{0}{1}'.format(YamjWatchedPath, path)
    path = '{0}.watched'.format(path)
    if not isfile(path):
        try:
            Debug('[Pchtrakt] Start to write file')
            f = open(path, 'w')
            f.close()
            msg = ' [Pchtrakt] I have created the file {0}'.format(path)
            pchtrakt.logger.info(msg)
            pchtrakt.CreatedFile = 1
        except IOError, e:
            pchtrakt.logger.exception(e)
            pchtrakt.CreatedFile = 1
    else:
        pchtrakt.CreatedFile = 2

def UpdateXMLFiles(pchtrakt):
    try:
        if  updatexmlwatched:
            checkpath = YamjPath.encode('utf-8')
            #Check path is correct
            if not isfile(checkpath + 'Other_All_1.xml'):
                Debug('[Pchtrakt] Somthing wrong with jukebox path, using ' + checkpath)
                Debug('[Pchtrakt] Trying to find correct path...')
                x = listdir('/opt/sybhttpd/localhost.drives/NETWORK_SHARE/')
                rest = '/' + ('/'.join(checkpath.split('/')[6:]))
                for y in x:
                    if isfile('/opt/sybhttpd/localhost.drives/NETWORK_SHARE/' + y + rest + 'Other_All_1.xml'):
                        checkpath = '/opt/sybhttpd/localhost.drives/NETWORK_SHARE/' + y + rest
                        break
                if not checkpath.endswith('/'):
                    checkpath += '/'
            matchthis = pchtrakt.lastName.encode('utf-8')
            matchthisfull = ('/'.join(pchtrakt.lastPath.encode('utf-8').split('/')[-2:]))
            lookfor = matchthis[:-4].replace('&','&amp;')
            mod = 0
            if pchtrakt.isMovie:
                moviexml = moviexmlfind
                msg = ' [Pchtrakt] Starting Normal Movie xml update in ' + checkpath
                pchtrakt.logger.info(msg)
                previous = None
                name = unquote_plus(checkpath + lookfor + '.xml')
                Debug('[Pchtrakt] Looking at ' + name)
                if isfile(name):
                    tree = ElementTree.parse(name)
                    try:
                        SET = unquote_plus(tree.find('movie/sets/set').attrib['index'])
                    except AttributeError:
                        SET = '0'
                    Debug('[Pchtrakt] 1 ' + name)
                    for movie in tree.findall('movie'):
                        Debug('[Pchtrakt] 2 ' + name)
                        if movie.find('baseFilenameBase').text.encode('utf-8') == lookfor:#for  content in penContents:
                            Debug('[Pchtrakt] MATCH FOUND')
                            movie.find('watched').text = 'true'
                            for mfile in movie.findall('files/file'):
                                mfile.set('watched', 'true')
                                bak_name = name[:-4]+'.bak'
                                tree.write(bak_name, encoding='utf-8')
                                rename(bak_name, name)
                                txt = utilities.ss(name.replace(checkpath, '') + ' has been modified as watched')
                                Debug('[Pchtrakt] ' + txt)
                                mod += 1
                                break
                else:
                    pchtrakt.logger.info(' [Pchtrakt] Can not find file, check your jukebox path')
                try:
                    if SET != "0":
                        moviexml.insert(0,SET)
                        Debug('[Pchtrakt] Has Set_ file: ' + SET)
                    for xmlword in moviexml:
                        fileinfo = checkpath + xmlword + "*xml"
                        Debug('[Pchtrakt] ' + fileinfo)
                        for name in glob.glob(fileinfo):
                            Debug('[Pchtrakt] Looking for ' + lookfor + " in " + name)
                            if lookfor in open(name).read():#gets xml file name as name
                                Debug('[Pchtrakt] MATCH FOUND')
                                tree = ElementTree.parse(name)
                                for movie in tree.findall('movies/movie'):
                                    if movie.find('baseFilenameBase').text.encode('utf-8') == lookfor:
                                        if movie.attrib['isSet'] == "true" and SET != "0":
                                            Debug('[Pchtrakt] isset is true')
                                            raise OutToMainLoop()
                                        movie.find('watched').text = 'true'
                                        bak_name = name[:-4]+'.bak'
                                        tree.write(bak_name, encoding='utf-8')
                                        rename(bak_name, name)
                                        txt = utilities.ss(name.replace(checkpath, '') + ' has been modified as watched for ' + matchthis)
                                        Debug('[Pchtrakt] ' + txt)
                                        mod += 1
                                        previous = xmlword
                                        break
                                break
                except OutToMainLoop:
                    pass
            elif pchtrakt.isTvShow:
                tvxml = tvxmlfind
                doubleEpisode = 0
                epno = str(pchtrakt.episode_numbers).replace('[', '').replace(']', '')
                if version_info >= (2,7): #[@...=...] only available with python >= 2.7
                    if len(pchtrakt.episode_numbers)>1:
                        doubleEpisode = 1
                        first, last = [epno[0], epno[-1]]
                        xpath = "*/movie/files/file[@firstPart='{0}'][@lastPart='{1}'][@season='{2}']".format(first,last,str(pchtrakt.season_number))
                        pchtrakt.logger.info(' [Pchtrakt] Starting multi episode Tv xml update in '+ checkpath)
                    else:
                        xpath = "*/movie/files/file[@firstPart='{0}'][@season='{1}']".format(epno,str(pchtrakt.season_number))
                        pchtrakt.logger.info(' [Pchtrakt] Starting normal Tv xml update in '+ checkpath)
                else:
                    xpath = "*/movie/files/file"
                season_xml = insensitive_glob(pchtrakt.lastShowName)
                seasonb_xml = pchtrakt.DirtyName
                tvxml.extend(["Set_" + season_xml,seasonb_xml])
                Debug('[Pchtrakt] looking for ' + lookfor)
                for xmlword in tvxml:
                    fileinfo = checkpath + xmlword + "*.xml"
                    Debug('[Pchtrakt] scanning ' + xmlword)
                    for name in glob.glob(utilities.ss(fileinfo)):
                        Debug('[Pchtrakt] scanning ' + name)
                        if lookfor in open(name).read():
                            Debug("after name " + fileinfo)
                            tree = ElementTree.parse(name)
                            if xmlword == seasonb_xml:
                                if version_info >= (2,7):
                                    if doubleEpisode:
                                        zpath = "./movie/files/file[@firstPart='{0}'][@lastPart='{1}'][@season='{2}']".format(first,last,str(pchtrakt.season_number))
                                    else:
                                        zpath = "./movie/files/file[@firstPart='{0}'][@season='{1}']".format(epno,str(pchtrakt.season_number))
                                else:
                                    zpath = "./movie/files/file"
                            else:
                                zpath = xpath
                            for movie in tree.findall(zpath):
                                Debug('[Pchtrakt] looking for ' + matchthisfull)
                                Debug('[Pchtrakt]  found this ' + unquote_plus('/'.join(movie.find('fileURL').text.encode('utf-8').split('/')[-2:])))
                                if unquote_plus('/'.join(movie.find('fileURL').text.encode('utf-8').split('/')[-2:])) == matchthisfull:
                                    Debug('[Pchtrakt] MATCH FOUND')
                                    movie.set('watched', 'true')
                                    bak_name = name[:-4]+'.bak'
                                    tree.write(bak_name, encoding='utf-8')
                                    rename(bak_name, name)
                                    txt = name.replace(checkpath, '') + ' has been modified as watched'
                                    Debug('[Pchtrakt] ' + txt)
                                    mod += 1
                                    previous = xmlword
                                    break
                            break
            msg = ' [Pchtrakt] XML Update complete, %d xml file(s) were updated' % mod
            pchtrakt.logger.info(msg)
        elif RutabagaModwatched:
            lookfor = matchthis[:-4]
            msg = ' [Pchtrakt] Starting html update in '+checkpath
            pchtrakt.logger.info(msg)
            if pchtrakt.isMovie:
                fileinfo = checkpath + lookfor + ".html"
                content = open(fileinfo,'rb+').read()
                replacedText = content.replace('unwatched', 'watched') 
                if replacedText is not content:
                    open(fileinfo, 'w').write(replacedText)
                    txt = name.replace(checkpath, '') + ' has been modified as watched for ' + matchthis
                    pchtrakt.logger.info(' [Pchtrakt] ' + txt)
                else:
                    txt = name.replace(checkpath, '') + ' has NOT been modified as watched for ' + matchthis
                    pchtrakt.logger.info(' [Pchtrakt] ' + txt)
    except Exception as e:
        pchtrakt.CreatedFile = 0
        Debug('[Pchtrakt] %s - Error accured during xml updating, Its being looked into' % str(e))