import spydaap, spydaap.parser.mp3, spydaap.parser.ogg, spydaap.parser.flac

spydaap.parsers = [spydaap.parser.mp3.Mp3Parser(), 
                   spydaap.parser.flac.FlacParser(), 
                   spydaap.parser.ogg.OggParser()]

#to process .mov files
#from spydaap.parser import mp3,mov

#spydaap.server_name = "spydaap"
#spydaap.port = 3689

#top path to scan for media
#spydaap.media_path = "media"

#spydaap.cache_dir = 'cache'

spydaap.container_list.append(spydaap.playlists.Genre('reggae', ["reggae", "reggae: dub", "dub"]))
spydaap.container_list.append(spydaap.playlists.Recent('last 30 days', (60 * 60 * 24 * 30)))
spydaap.container_list.append(spydaap.playlists.YearRange('1970s', 1970, 1979))
spydaap.container_list.append(spydaap.playlists.Rating('top rated', 100))
