import configparser
import datetime
import os
import traceback

from deluge.ui.client import client
from plexapi.server import PlexServer
from twisted.internet import reactor, defer

PLEX_URL = 'http://10.0.0.6:32400'
PLEX_TOKEN = ''


def findWatchedEpisodes(plex, sectionName, days):
  cutoff = datetime.datetime.now() - datetime.timedelta(days)
  section = plex.library.section(sectionName)
  watched = {}
  for episode in section.searchEpisodes(unwatched=False):
    if episode.lastViewedAt < cutoff:
      for media in episode.media:
        for part in media.parts:
          path = part.file
          watched[os.path.basename(path)] = path

  return watched


def deleteFiles(watchedFiles, debug=False):
  deletedFiles = 0
  deletedBytes = 0
  for file in watchedFiles.values():
    if os.path.exists(file):
      deletedFiles += 1
      deletedBytes += os.path.getsize(file)
      if debug:
        print 'Will delete %s' % file
      else:
        os.remove(file)
  if deletedFiles > 0:
    if debug:
      print 'Will delete %d GB in %d files' % (deletedBytes / 1024 / 1024 / 1024, deletedFiles)
    else:
      print 'Deleted %d GB in %d files' % (deletedBytes / 1024 / 1024 / 1024, deletedFiles)

@defer.inlineCallbacks
def deleteTorrents(delugeHost, delugeUsername, delugePassword, watchedFiles):
  try:
    yield client.connect(host=delugeHost, username=delugeUsername, password=delugePassword)
    torrents = yield client.core.get_torrents_status({}, [])

    for torrent in torrents.values():
      for file in torrent['files']:
        if file in watchedFiles.keys():
          print 'Removing torrent ' % torrent
  except Exception as e:
    traceback.print_exc()

  finally:
    client.disconnect()
    reactor.stop()


if __name__ == '__main__':
  config = configparser.ConfigParser()
  config.read(os.path.expanduser('~/.plex-delete-watched'))
  plexConfig = config['Plex']
  plexUrl = plexConfig['url']
  plexToken = plexConfig['token']
  if plexToken== '':
    plexToken = None
  plex = PlexServer(plexUrl, plexToken)
  watchedFiles = findWatchedEpisodes(plex, '1. TV', 14)

  deleteFiles(watchedFiles, True)

  delugeConfig = config['Deluge']

  deleteTorrents(delugeConfig['host'], delugeConfig['username'], delugeConfig['password'], watchedFiles)

  reactor.run()
