Plugin Development Guide
========================

.. note:: These instructions always track current Exaile trunk, and may not
          be fully compatible with stable releases.  It is recommended that
          you develop plugins against trunk, so that you can submit patches
          to trunk if need be during the creation of your plugin, and so
          that your plugin can easily be merged into trunk when it is ready.

Style
-----

If you plan to submit your plugin for inclusion in Exaile, please read and
follow the guidelines in the :ref:`code_guidelines`.

Basic plugin structure
----------------------

Plugins in Exaile 3.x+ are handled slightly differently than in the past.
Each plugin has its own directory in ``~/.local/share/exaile/plugins/``. In order
for your plugin to be recognized as valid by Exaile, it needs to have at least
two files in the plugin directory (``~/.local/share/exaile/plugins/myplugin/``):

* ``__init__.py``
* ``PLUGININFO``

The format of the ``PLUGININFO`` is as follows::

    Version='0.0.1'
    Authors=['Your Name <your@email.com>']
    Name=_('Plugin Name')
    Description=_('Something that describes your plugin. Also mention any extra dependencies.')
    Category=_('Development')
    
The following two attributes are optional:

* `Platforms` - A list of the platforms your plugin works on. If you have no
  specific requirements, omitting this argument or using an empty list is
  fine. The values of the list are the sys.platform value.
* `RequiredModules` - A list of additional modules required by your plugin.
  Modules that Exaile already require (e.g. mutagen) don't need to be specified.
  To specify GObject Introspection libraries, prefix it with ``gi:``, e.g.
  ``gi:WebKit2``.

.. note:: Name and Description are what show up in the plugin manager.
          Category is used to list your plugin alongside other plugins.
          Platforms and RequiredModules are used to filter out the plugin
          on inappropriate platforms.

Before Exaile 3.4, ``__init__.py`` was required to define at least two methods,
``enable()`` and ``disable()``. However, Exaile 3.4 introduced a new way to write
plugins which will eliminate a lot of unnecessary boilerplate for plugin
authors. We will use this model below:

.. code-block:: python

    class MyPlugin:
    
        def enable(self, exaile):
            print('You enabled me!')
            
        def disable(self, exaile):
            print('I am being disabled')

    
    plugin_class = MyPlugin

For many types of plugins, this might be enough. However, there are other
optional methods you can define in your plugin object.

* ``on_gui_loaded`` - This will be called when the GUI is ready, or immediately
  if already done
* ``on_exaile_loaded`` - This will be called when exaile has finished loading,
  or immediately if already done
* ``teardown`` - This will be called when exaile is unloading

These methods may be necessary for your plugin because plugins can only
access Exaile’s infrastructure when Exaile itself finishes loading.
The first ``enable()`` method is called when Exaile is partway through
loading. But since we can't do anything until Exaile finishes loading, we
can add ``on_exaile_loaded`` to our object that is called when Exaile finishes
loading. Some plugins need to modify state earlier in the startup process,
hence the need for this separation.

The ``exaile`` object in the above example is an instance of a class called
Exaile, which is defined in ``xl/main.py``. This class is a base for everything
in the program.

You can get a handle on various objects in Exaile by looking at the members
of this class.

Something (slightly) more useful
--------------------------------

Here is an example of a plugin that will, when a track is played, show the
track information in a ``MessageDialog``. It demonstrates a callback on an event,
and getting the Gtk.Window object of Exaile to use as a parent for a MessageBox.

The ``PLUGININFO`` is as follows::

    Version='0.0.1'
    Authors=['Me <me@internets.com>']
    Name='Tutorial Plugin'
    Description='Plugin to demonstrate how to make a plugin.'

and the ``__init__.py`` is as follows

.. code-block:: python

    '''
        This plugin will show an obnoxious Gtk.MessageDialog that
        won't disappear, when a track is played. The MessageDialog
        will contain the information of the currently playing track.
    '''
    
    from xl import event
    from gi.repository import Gtk
    
    # The main functionality of each plugin is generally defined in a class
    # This is by convention, and also makes programming easier
    class TutorialPlugin:
    
        def enable(self, exaile):
            '''This method is called when the plugin is loaded by exaile'''
            
            # We need a reference to the main Exaile object in order to set the
            # parent window for our obnoxious MessageDialog
            self.exaile = exaile
            
        def disable(self, exaile):
            '''This method is called when the plugin is disabled. Typically it is used for
               removing any GUI elements that we may have added in _enable()'''
            self.show_messagebox("Byebye!")
        
        def on_exaile_loaded(self):
            '''Called when exaile is ready for us to manipulate it'''
            
            #The reason why we dont use show_messagebox here is it hangs the GUI
            #which means it would hang Exaile as soon as you restart, because all
            #enabled plugins are loaded on start.
            print('You enabled the Tutorial plugin!')  
            
            # Add a callback for the 'playback_track_start' event.
            # See xl/event.py for more details.
            event.add_callback(self.popup_message, 'playback_track_start')
            
           
        def popup_message(self, type, player, track):
            # The Track object (defined in xl/track.py) stores its data in lists
            # Convert the lists into strings for displaying
            title = track.get_tag_display('title')
            artist = track.get_tag_display('artist')
            album = track.get_tag_display('album')
            message = "Started playing %s by %s on %s" % (title, artist, album)
            self.show_messagebox(message)
        
        def show_messagebox(self, message):
            # This is the obnoxious MessageDialog. Due to (something to do with threading?)
            # it will steal, and never relinquish, focus when it is displayed.
            dialog = Gtk.MessageDialog(self.exaile.gui.main.window, 0,
                                       Gtk.MessageType.INFO, Gtk.ButtonsType.OK, message)
            dialog.run()
            dialog.destroy()
          
    
    plugin_class = TutorialPlugin

Have a look in the comments for an explanation of what everything is doing.

Adding a track to the Playlist
------------------------------

This is relatively simple. A Playlist consists of the actual graphical
representation of a playlist (see ``xlgui/playlist.py``) and its underlying
Playlist object (see ``xl/playlist.py``). Any changes made to the underlying
playlist object are shown in the graphical representation. We will be
appending Track objects to this underlying playlist.

First you need to get a handle on the underlying Playlist:

.. code-block:: python

    playlist_handle = exaile.gui.main.get_selected_playlist().playlist

Then, you need to create a Track object (defined in ``xl/track.py``). The
method to do this from a local file versus a URL is slightly different.

For a local source:

.. code-block:: python

    from xl import trax
    path = "/home/user/track.ogg" #basically, just specify an absolute path
    myTrack = trax.Track(path)

For a url:

.. code-block:: python

    from xl import trax
    url = "http://path/to/streaming/source" 
    myTrack = trax.get_tracks_from_uri(url)

You can set the track information like this:

.. code-block:: python

    myTrack.set_tags(title='Cool Track',
                     artist='Cool Person',
                     album='Cool Album')

Once you have a Track object, and a handle on the Playlist you would like
to add the track to, you can proceed to add the track:

.. code-block:: python

    playlist_handle.add(myTrack)

Note that ``get_tracks_from_uri()`` returns a list, so you will need to use the
method for adding multiple tracks if your Track object was created this way.
You can also create your own list of Track objects and add them all in one
go like this too:

.. code-block:: python

    playlist_handle.add_tracks(myTrack)

This is pretty much all you need to do to add a track to the playlist. An
example in a plugin might be:

.. code-block:: python

    from xl import event, trax
    
    class PlaylistExample:
   
        def enable(self, exaile):
            self.exaile = exaile
            
        def disable(self, exaile):
            pass
   
        def on_gui_loaded(self):
            self.playlist_handle = self.exaile.gui.main.get_selected_playlist().playlist
            
            local_tr = self.create_track_from_path('/home/user/track.ogg')
            remote_tr = self.create_track_from_url('http://site.com/track.ogg')
            self.add_single_to_playlist(local_tr)
            self.add_multiple_to_playlist(remote_tr)
        
        def create_track_from_path(self, path):
            return trax.Track(path)

        def create_track_from_url(self, url):
            return trax.get_tracks_from_uri(url)

        def add_single_to_playlist(self, track):
            self.playlist_handle.add(track)

        def add_multiple_to_playlist(self, tracks):
            self.playlist_handle.add_tracks(tracks)
    
    
    plugin_class = PlaylistExample

You can do more things when adding a track than simply specifying a track
object to add, see the methods in the class Playlist (``xl/playlist.py``) for more
details.

Adding another page to the left-hand Notebook
---------------------------------------------

This is done pretty easily. Basically, you need to subclass ``xlgui.panel.Panel``
and register a provider advertising your panel.

The subclass needs to have two attributes:

* ``ui_info`` - This defines the location of the .glade file that will be loaded
  into the notebook page (This file must be in Gtk.Builder format, not glade format)
* ``name`` - This is the name that will show on the notebook page, such as "MyPlugin"

.. code-block:: python

    from xl import providers
    from xlgui import panel
    
    # Note: The following uses the exaile object from the enable() method. You
    # might want to call this from the on_gui_loaded function of your plugin.
    page = MyPanel(exaile.gui.main.window)
    providers.register('main-panel', page)
    
    # to remove later:
    providers.unregister('main-panel', page)
       
    class MyPanel(panel.Panel):
        
        #specifies the path to the gladefile (must be in Gtk.Builder format) and the name of the Root Element in the gladefile
        ui_info = (os.path.dirname(__file__) + "mypanel_gladefile.glade", 'NameOfRootElement')    
    
        def __init__(self, parent):
            panel.Panel.__init__(self, parent)
            
            #This is the name that will show up on the tab in Exaile
            self.name = "MyPlugin"
            
            #typically here you'd set up your gui further, eg connect methods to signals etc

That's pretty much all there is to it. To see an actual implementation,
have a look at ``xlgui/panel/collection.py`` or take a look at the Jamendo plugin.

Setting the cover art for a track
---------------------------------

This is done by subclassing ``CoverSearchMethod`` and adding and instance of
the subclass the existing list. When Exaile plays a track with no cover,
it uses all the methods in its ``CoverSearchMethod`` list to try and find a cover.

A ``CoverSearchMethod`` must define:

* ``name`` - The name of the ``CoverSearchMethod``, used for removing it from the list once its been added
* ``type`` - The type of the ``CoverSearchMethod`` (local, remote)
* ``find_covers(self, track, limit=-1)`` - This is the method that is called
  by Exaile when it utilises the ``CoverSearchMethod``. This method must return
  an absolute path to the cover file on the users harddrive.

Here is an example CoverSearchMethod (taken from the Jamendo plugin). It
searches Jamendo for covers, downloads the cover to a local temp directory
and returns the path to the downloaded cover.

.. code-block:: python

    import urllib.request
    import hashlib
    from xl.cover import CoverSearchMethod, NoCoverFoundException
    
    class JamendoCoverSearch(CoverSearchMethod):
        name = 'jamendo'
        type = 'remote'
    
        def __init__(self):
            CoverSearchMethod.__init__(self)
    
        def find_covers(self, track, limit=-1):
            jamendo_url = track.get_loc_for_io()
    
            cache_dir = self.manager.cache_dir
            if (not jamendo_url) or (not ('http://' and 'jamendo' in jamendo_url)):
                raise NoCoverFoundException
    
            #http://stream10.jamendo.com/stream/61541/ogg2/02%20-%20PieRreF%20-%20Hologram.ogg?u=0&h=f2b227d38d
            split=jamendo_url.split('/')
            track_num = split[4]
            image_url = jamapi.get_album_image_url_from_track(track_num)
    
            if not image_url:
                raise NoCoverFoundException
    
            local_name = hashlib.sha1(split[6]).hexdigest() + ".jpg"
            covername = os.path.join(cache_dir, local_name)
            urllib.request.urlretrieve(image_url, covername)
    
            return [covername]

You can then add it to the list of ``CoverSearchMethods`` for Exaile to try like this:

.. code-block:: python

    exaile.covers.add_search_method(JamendoCoverSearch())

And remove it like this:

.. code-block:: python

    exaile.covers.remove_search_method_by_name('jamendo')


Make strings translatable
-------------------------

Every message should be written in English and should be translatable. The
following example shows how you can make a string translatable:

.. code-block:: python

    from xl.nls import gettext as _
    print(_('translatable string'))


Saving/Loading arbitrary settings
---------------------------------

This is quite easy. It's probably quicker to just show some code instead
of trying to explain it:

.. code-block:: python

    from xl import settings
    
    #to save a setting:
    setting_value = 'I am the value for this setting!'
    settings.set_option('plugin/pluginname/settingname', setting_value)
    
    #to get a setting
    default_value = 'If the setting doesn't exist, I am the default value.'
    retrieved_setting = settings.get_option('plugin/pluginname/settingname', default_value)

That's all there is to it. There is a few restrictions as to the
datatypes you can save as settings, see ``xl/settings.py`` for more details.

Searching the collection
-------------------------

The following method returns an list of similar tracks to the current
playing track:

.. code-block:: python

    exaile.dynamic.find_similar_tracks(exaile.player.current, 5) #the second optional argument is the limit

This method returns an list of tuples, which consist of the match rate and the artist's name:

.. code-block:: python

    exaile.dynamic.find_similar_artists(exaile.player.current)

If you would like to search the collection for a specific artist, album or
genre, you can use the following code:

.. code-block:: python

    from xl.trax import search
    
    artist = 'Oasis'
    tracks = [x.track for x in search.search_tracks_from_string(
               exaile.collection, ('artist=="%s"'%artist))]
               
    genre = 'pop'
    tracks = [x.track for x in search.search_tracks_from_string(
               exaile.collection, ('genre=="%s"'%genre))]
               
    album = 'Hefty Fine'
    tracks = [x.track for x in search.search_tracks_from_string(
               exaile.collection, ('album=="%s"'%album))]

You can search the collection also for different assignments, like the last
played tracks, the most recently added tracks or the tracks, which were
played most often. Here you see an example to display the most recently
added tracks:

.. code-block:: python

    from xl.trax import search
    from xl.trax.util import sort_tracks
    
    tracks = [x.track for x in search.search_tracks_from_string(exaile.collection, ('! %s==__null__' % '__last_played'))]
    tracks = sort_tracks(['__last_played'], tracks, True) #sort the tracks by the last playing
   
The other keywords are ``__date_added`` and ``__playcount``

Exaile D-Bus
------------

Here is a simple example how to use the D-Bus object:

.. code-block:: python

    #!/usr/bin/env python3
    
    from io import BytesIO
    import sys

    import dbus
    import Image
    
    def test_dbus():
        bus = dbus.SessionBus()
        try:
            remote_object = bus.get_object("org.exaile.Exaile","/org/exaile/Exaile")
            iface = dbus.Interface(remote_object, "org.exaile.Exaile")
            if iface.IsPlaying():
                title = iface.GetTrackAttr("title")
                print('Title:', title)
                album = iface.GetTrackAttr("album")
                print('Album:', album)
                artist = iface.GetTrackAttr("artist")
                print('Artist:', artist)
                genre = iface.GetTrackAttr("genre")
                print('Genre:', genre)
                dbusArray = iface.GetCoverData()
                coverdata = bytes(dbusArray)
                if coverdata:
                    im = Image.open(BytesIO(coverdata))
                    im.show()
            else:
                print("Exaile is not playing.")
        except dbus.exceptions.DBusException:
            print("Exaile is not running.")
    
    if __name__ == "__main__":
        test_dbus()

Please check out ``xl/xldbus.py`` for further method signatures.

Playback events
---------------

Since playback events can occur far before the main GUI object or even the
``exaile`` object is loaded, connecting to them in advance is required. To 
do this, in your ``__init__`` method:

.. code-block:: python

    event.add_callback(self.on_playback_player_start, 'playback_player_start')


Distributing the Plugin
-----------------------

Create a Plugin Archive
^^^^^^^^^^^^^^^^^^^^^^^

Basically, you just need to tar up your plugin's directory, and rename the
tarfile to <name_of_plugin_directory>.exz

You will need to develop your plugin with a similar hierarchy to the following::

    root --
         \ -- __init__.py
         \ -- PLUGININFO
         \ -- data
           \ -- somefile.glade
           \ -- somefile.dat
         \ -- images
           \ -- somefile.png

The archive should be named with the extension *.exz*. The name of the
plugin.exz file needs to match the name of the plugin directory.

So in the above example, you would need to call your plugin *root.exz* in
order for it to be accepted by Exaile.

exz files can optionally be compressed, using either gzip or bzip2. the
extension remains the same.

This is all you need to do to make a plugin archive.

Exaile API
----------

Now you know the basics about programming plugins for Exaile, but there
are many more useful classes you may need. You can get an overview about
the classes and their use by going through the :ref:`api_docs`.

Building your own version of this documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the Python package manager (`pip <https://pip.pypa.io/en/stable/>`_)
to install sphinx:

.. code-block:: sh
  
    $ pip install sphinx
    
    # or on windows  
    $ py -m pip install sphinx

Then you can run the following command in a terminal:

.. code-block:: sh

    $ cd doc && make html

You'll find the documentation in ``doc/_build/html``.
