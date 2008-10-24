LastFMProxy v1.3
(c) 2005-2007 Vidar Madsen


1. Introduction

LastFMProxy is a proxy server for the last.fm radio streams. It allows you
to use your regular old audio player to listen to the last.fm streams. It
does this by acting as a player itself, connecting to the server on your
behalf, but instead of playing the stream, it simply relays it to
whichever other application connecting to it.


2. Basic usage

First, make sure you have a Python environment installed. You might have
one already, but if not, go to http://www.python.org/ftp/python/ and
download one suitable for your operating system. (If you're using a
Windows operating system, you will need to get Windows Installer to
install Python.)

Now, uncompress and unpack the archive file. In Unix-like operating systems,
you can do this by running the command:
  tar xvzf lastfmproxy.tar.gz

Under Windows, WinZip or a similar compression tool should do fine.

Now go into the directory "lastfmproxy", and modify the file "config.py"
and set our last.fm login and password. If you need (or want) to use an
external proxy for web access, you must set also set useproxy to "True",
and set the proxy host name and port.

The config file has a "bind_address" options, which tells the proxy which
network interface to listen on. The default is to bind only to the localhost
interface (127.0.0.1). If you want to be reach the proxy from other hosts
on the network, change this to either the machine's IP address or just use
"0.0.0.0", which binds it to all interfaces available. Note that this is
potentially less secure than binding only to the localhost IP, though.

Now you can start the proxy. This is done by simply running "main.py".
It will then show the URL at which you must aim your player. Mark and
copy this URL to your clipboard or similar.

Finally, fire up your web browser of choice. Select "Open location" or
something similar, and paste the URL there. You should see the proxy
status page, vaguely resembling the last.fm player. Click "Start radio",
and you're done! (You can also bookmark the URL in your browser for next
time, to save you a little bit of work.)

By default, the server starts playing your last station (or your "musical
neighbours" station, if it couldn't be determined for some reason).

Normally you will want to use the "changestation" script to change channels
(see paragraph below). If not, you can use the web interface directly. The
web interface is not perfect, but it's not too hard to do manually. To play
another station, you can simply modify the browser URL; Just append the
"lastfm:" station address directly to your proxy URL.

Some example URLs;
  http://localhost:1881/lastfm://globaltags/rock
  http://localhost:1881/lastfm://artist/Madonna/similarartists
  http://localhost:1881/lastfm://user/vidarino/neighbours

You should get the picture. :) One thing, though; when you're editing URLs,
make sure you replace spaces with "%20" (e.g. "hiphop" becomes "hip%20hop".)
The easiest shortcut is to browse the last.fm site, and "Copy link location"
when you see a station you like, and simply paste it at the end of the
browser location in the proxy window.

Also, whenever you change stations, they will be added to the station history
pulldown menu in the lower right, where they quickly and easily can be fetched
again.

Note; You can also select a station directly when starting the player. Just
open an URL on the form "http://localhost:1881/globaltags/jazz.m3u" to start
streaming *and* select a station at the same time.

This is particularly useful if you don't have a browser at all, and just want
to listen to music. Under Linux, using mplayer, you can listen to any channel
by starting the proxy, then launch:
  mplayer -playlist "http://localhost:1881/globaltags/metal.m3u"


3. Configuring the changestation.py script (Mozilla Firefox only)

Here's how to make the lastfm://station links work:

- In Firefox, open the location "about:config"
- Right-click, select "New String"
- As name, enter "network.protocol-handler.app.lastfm", "OK"
- As value, enter the full path to the included "changestation.py" script
  (e.g. "C:\Program Files\lastfmproxy\changestation.py"), then "OK"

That should do the trick. Now, when you click on station link on the last.fm
site, the proxy should catch on and start playing your selection in a few
seconds.


4. Caveats

Nothing is perfect. Here are some things you should know:

- The author has only tested it under Linux. But user feedback seems to
indicate success under various Windows versions and Mac OS X.

- It is probably full of bugs. Hopefully the most annoying of these can get
stomped out eventually.

- The Record to Profile and Discovery Mode checkboxes lag. RTP will take a
few seconds to toggle, while Discovery will not update until the next song
change. This is a known issue, but I'm not sure about the right way to fix
it (if at all). The checkboxes reflect what the server reports about its
current status, and not what it will do in the future.


5. Troubleshooting

I can't promise much support, but feedback is always welcome.

You can drop me a message on last.fm (nick "vidarino"), or send me
a mail at "vidarino at gmail dot com".

Also, there's now a LastFMProxy group on the last.fm site. Feel free to
join us:
  http://www.last.fm/group/LastFMProxy



