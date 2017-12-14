import datetime
import os
import traceback

from deluge.log import setupLogger
from deluge.ui.client import client
from plexapi.server import PlexServer
from twisted.internet import reactor, defer

DELUGE_PASSWORD = 'nando'

DELUGE_USERNAME = 'al'

DELEUGE_HOST = '127.0.0.2'

PLEX_URL = 'http://127.0.0.2:32400'
PLEX_TOKEN = 'a4ZepkJYKnrKdZrqKLgs'


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
def deleteTorrents(watchedFiles):
  try:
    yield client.connect(host=DELEUGE_HOST, username=DELUGE_USERNAME, password=DELUGE_PASSWORD)
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
  plex = PlexServer(PLEX_URL, PLEX_TOKEN)
  watchedFiles = findWatchedEpisodes(plex, '1. TV', 14)

  deleteFiles(watchedFiles, False)
  deleteTorrents(watchedFiles)

  reactor.run()
