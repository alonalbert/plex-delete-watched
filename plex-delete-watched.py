import datetime
from plexapi.server import PlexServer


def findWatchedEpisodes(sectionName, days):
    cutoff = datetime.datetime.now() - datetime.timedelta(days)
    section = plex.library.section(sectionName)
    watched = []
    for episode in section.searchEpisodes(unwatched=False):
        
        watched.append(episode)
    return watched

url = 'http://127.0.0.2:32400'
token = 'a4ZepkJYKnrKdZrqKLgs'
plex = PlexServer(url, token)

watched = findWatchedEpisodes('1. TV', 7)

print len(watched)