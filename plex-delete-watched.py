import configparser
import datetime
import os
import sys
import traceback

from deluge.ui.client import client
from plexapi.server import PlexServer
from twisted.internet import reactor, defer

class Main:
  # If this is true, will only print stuff. Won't actually delete anything
  fakeDelete = True
  plexFiles = set([])
  watchedFiles = {}

  config = None

  def __init__(self, fakeDelete):
    self.fakeDelete = fakeDelete
    self.config = configparser.ConfigParser()
    self.config.read(os.path.expanduser('~/.plex-delete-watched'))
    pass


  def run(self):
    # Read plex sections and populate plexFiles & watchedFiles
    self.processSections()

    # Delete all watched files from disk.
    self.deleteFiles()

    # Delete torrents who have all their files watched
    self.deleteTorrents()

    reactor.run()

  def processSections(self):
    plexConfig = self.config['Plex']
    plexUrl = plexConfig['url']
    plexToken = plexConfig['token']
    if plexToken== '':
      plexToken = None
    plex = PlexServer(plexUrl, plexToken)

    sections = self.config['Sections']
    for key, value in sections.iteritems():
        if key.startswith('name'):
          sectionName = value
          sectionDuration = int(sections['duration' + key[4:]])
          self.processSection(plex, sectionName, sectionDuration)

  def processSection(self, plex, sectionName, days):
    cutoff = datetime.datetime.now() - datetime.timedelta(days)
    section = plex.library.section(sectionName)
    for episode in section.searchEpisodes():
      for media in episode.media:
        for part in media.parts:
          path = part.file
          filename = os.path.basename(path)
          self.plexFiles.add(filename)
          if episode.isWatched and episode.lastViewedAt < cutoff:
            self.watchedFiles[filename] = path

  def deleteFiles(self):
    deletedFiles = 0
    deletedBytes = 0
    for file in self.watchedFiles.values():
      if os.path.exists(file):
        deletedFiles += 1
        deletedBytes += os.path.getsize(file)
        if self.fakeDelete:
          print 'Will delete %s' % file
        else:
          os.remove(file)
    if deletedFiles > 0:
      if self.fakeDelete:
        print 'Will delete %d GB in %d files' % (deletedBytes / 1024 / 1024 / 1024, deletedFiles)
      else:
        print 'Deleted %d GB in %d files' % (deletedBytes / 1024 / 1024 / 1024, deletedFiles)

  @defer.inlineCallbacks
  def deleteTorrents(self):
    delugeConfig = self.config['Deluge']

    try:
      yield client.connect(host=delugeConfig['host'], username=delugeConfig['username'], password=delugeConfig['password'])
      torrents = yield client.core.get_torrents_status({}, [])

      for torrent in torrents.values():
        isTorrentServedByPlex = False
        isTorrentWatched = False
        for file in torrent['files']:
          filename = os.path.basename(file['path'])
          if filename in self.plexFiles:
            isTorrentServedByPlex = True
          if filename not in self.watchedFiles.keys():
            isTorrentWatched = False
            break
          isTorrentWatched = True
        if isTorrentServedByPlex and isTorrentWatched:
          if self.fakeDelete:
            print "Will remove torrent %s" % torrent
    except Exception as e:
      traceback.print_exc()

    finally:
      client.disconnect()
      reactor.stop()

if __name__ == '__main__':
  main = Main(False)

  main.run()
