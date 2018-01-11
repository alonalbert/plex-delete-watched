#!/usr/bin/python2.7
#
import requests
import configparser
import datetime
import logging
import os
import sys
import traceback

from deluge.ui.client import client
from plexapi.server import PlexServer
from twisted.internet import reactor, defer

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

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
    self.path = self.config['General']['path']
    pass

  def run(self):
    avail = os.statvfs(self.path).f_bavail

    # Read plex sections and populate plexFiles & watchedFiles
    self.processSections()

    # Delete all watched files from disk.
    self.deleteFiles()

    # Delete torrents who have all their files watched
    self.deleteTorrents()

    reactor.run()

    stats = os.statvfs(self.path)
    freed = (stats.f_bavail - avail) * stats.f_bsize / 1024 /1024
    if 1 > 0:
      pushoverConfig = self.config['Pushover']
      requests.post('https://api.pushover.net/1/messages.json', data={
        'user': pushoverConfig['user'],
        'token': pushoverConfig['token'],
        'message': '%dmb freed on disk' % freed,
      })

  def processSections(self):
    plexConfig = self.config['Plex']
    plexUrl = plexConfig['url']
    plexToken = plexConfig['token']
    if plexToken == '':
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
            self.watchedFiles[filename] = (path, episode.lastViewedAt)

  def deleteFiles(self):
    deletedFiles = 0
    deletedBytes = 0
    for file, watchedAt in self.watchedFiles.values():
      if os.path.exists(file):
        deletedFiles += 1
        deletedBytes += os.path.getsize(file)
        print 'Deleting %s (watched at %s)' % (file, watchedAt)
        if not self.fakeDelete:
          os.remove(file)
    if deletedFiles > 0:
      print 'Deleted %d GB in %d files' % (deletedBytes / 1024 / 1024 / 1024, deletedFiles)

  @defer.inlineCallbacks
  def deleteTorrents(self):
    delugeConfig = self.config['Deluge']
    generalConfig = self.config['General']
    deleteRarDurationSec = int(generalConfig['delete-rar-duration']) * 60 * 60 * 24

    labels = {}
    labelsConfig = self.config['Labels']
    for key, value in labelsConfig.iteritems():
      if key.startswith('name'):
        index = key[4:]
        name = value
        labels[name] = {
          'duration': (int(labelsConfig['duration' + index]) * 60 * 60 * 24),
          'delete-data': labelsConfig['deleteData' + index] == 'True'
        }

    try:
      yield client.connect(host=delugeConfig['host'], username=delugeConfig['username'],
                           password=delugeConfig['password'])
      torrents = yield client.core.get_torrents_status({}, [])

      for torrentId, torrent in torrents.iteritems():
        filename = None
        deleteTorrent = False
        deleteData = False
        message = 'Deleting torrent %s' % torrent['name']

        isTorrentServedByPlex = False
        isTorrentWatched = False
        isRar = False
        for file in torrent['files']:
          filename = os.path.basename(file['path'])
          if filename.endswith('.rar'):
            isRar = True
          if filename in self.plexFiles:
            isTorrentServedByPlex = True
          if filename not in self.watchedFiles.keys():
            isTorrentWatched = False
            continue
          isTorrentWatched = True
        if isTorrentServedByPlex:
          if isTorrentWatched:
            deleteTorrent = True
            deleteData = True
            message = message + " (watched at %s)" % self.watchedFiles[filename][1]

        elif isRar:
          if torrent['seeding_time'] > deleteRarDurationSec:
            deleteTorrent = True
            deleteData = True
            message = message + " (seeding time: %d days)" % (torrent['seeding_time'] / 60 / 60 / 24)
        else:
          label = torrent['label']
          labelInfo = labels.get(label)
          if labelInfo is not None:
            if torrent['seeding_time'] > labelInfo['duration']:
              deleteTorrent = True
              message = message + " (seeding time: %d days)" % (torrent['seeding_time'] / 60 / 60 / 24)
              if labelInfo['delete-data']:
                deleteData = True

        if deleteTorrent:
          print(message)
          if deleteData:
            print('  Deleting torrent data')
          if not self.fakeDelete:
            yield client.core.remove_torrent(torrentId, deleteData)

    except Exception as e:
      traceback.print_exc()

    finally:
      client.disconnect()
      reactor.stop()


if __name__ == '__main__':
  fake = False
  if len(sys.argv) > 1 and sys.argv[1] == '--fake':
    fake = True
  Main(fake).run()
