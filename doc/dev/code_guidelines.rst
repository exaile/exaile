
.. _code_guidelines:

Code guidelines
===============

Page to hold style and practice guidelines for contributions to Exaile.
Patches to make the existing core codebase follow these guidelines are
always welcome and a good way to start learning about the internal
workings of Exaile.

Note that this document will generally reflect the 'trunk' version of
Exaile, and may not be fully applicable to stable releases. If in doubt,
ask!

Basic Style
-----------

Exaile uses the `black <https://github.com/ambv/black>`_ code formatter to
enforce a consistent style across the project. You can run black like so:

.. code-block:: sh
    
    make format

For things that the code formatter doesn't do for you, the following applies:

-  In general, `PEP 8 <https://www.python.org/dev/peps/pep-0008/>`_ applies
-  Keep imports on one line each to make sure imports cannot be missed:

.. code-block:: python

    # Not recommended
    from gi.repository import Gtk, GLib, GObject
    
    # Preferred
    from gi.repository import Gtk
    from gi.repository import GLib
    from gi.repository import GObject

-  Always write out variable names to keep them descriptive. Thus ``notebook_page`` is to
   be preferred over ``nb``.

   -  Exceptions:

      -  Names which are prone to spelling mistakes like ``miscellaneous`` and
         ``utilities``. Here ``misc`` and ``util`` are perfectly fine.
      -  If a very-long-named (like foooooo.bar\_baz\_biz\_boz) variable
         or function needs to be accessed by a large percentage of lines
         in a small space, it may be shortened as long as 1) the name it
         is shortened to is consistent across all uses of this shortcut,
         and 2) the shortcut is limited in scope to just the area where
         it is used repeatedly. If in doubt, do NOT use this exception.

-  Try to group related methods within a class, this makes it easier to
   debug. If it's a particularly significant group of methods, mark them
   with a triple-comment at the beginning and end, like so:

.. code-block:: python

    ### Methods for FOOBAR ###
    ## more-detailed description (if needed)
    def meth1(self):
        ...
    
    ### End FOOBAR ###

-  The closing triple-comment may be omitted if at the end of a class or
   if another triple-comment starter comes after it.
-  If you need a collection of constants for some purpose, it is
   recommended to use the ``enum`` function from ``xl.common`` to construct one. The constant
   type should be UpperCamelCase, the possible values UPPERCASE:

.. code-block:: python

    from xl.common import enum
    
    ActionType = enum(ADD='add', EDIT='edit', ...)
    
    # ...
    
    if action.type == ActionType.EDIT:
        # ...

Documentation
-------------

-  Always add docstrings to your public classes, methods and functions.
-  Follow the `Sphinx <https://www.sphinx-doc.org>`__ format for
   documentation within docstrings.

Events and Signals
------------------

-  Items internal to Exaile (ie. anything under ``xl/``) should generally
   prefer ``xl.event`` over ``GObject`` signals. Items that tie deeply into
   the (GTK) UI should prefer ``GObject`` signals over ``xl.event``.
-  Keep in mind all events are synchronous - if your callback might take
   a while, run it in a separate thread.
-

    -  Make sure that every access to GTK UI components is run in the
       GTK main thread. Otherwise unpredictable issues can occur
       including crashes due to cross-thread access. This can be
       accomplished by running the specific code through the
       `GLib.idle\_add <https://lazka.github.io/pgi-docs/GLib-2.0/functions.html#GLib.idle_add>`__
       function. Please use the function decorator ``common.idle_add``.
       A typical mistake:

.. code-block:: python

            def __init__(self):
                """
                    Set up a label in the GTK main thead and
                    connect to the playback_track_start event
                """
                self.label = Gtk.Label()
                event.add_callback(self.on_playback_track_start, 'playback_track_start')
            
            def on_playback_track_start(event, player, track):
                """
                    Serious problem: this event is run in a
                    different thread, a crash is likely to occur
                """
                self.label.set_text(track.get_tag_display('title'))

-  Event names should be all lower-case, using underscores to separate
   words.

   -  Names should be prefixed by the general name indicating the
      category or sender of the event. For example, events sent from
      ``xl.player`` start with a ``playback_`` prefix.
   -  The remainder of the name should indicate what action just
      happened. eg. ``playback_player_pause``.
   -  The data sent in an event should be whatever piece (or pieces) of
      data are most relevant to the event. For example, if the event is
      signaling that a state has changed, the new state should be sent,
      or if the event indicates that an item was added, the new item
      should be sent.

-  Callbacks for ``GObject`` and ``xl.event`` should always be named "``on_``"
   + the name of the event. This avoids confusion and draws a line between
   regular methods and signal/event callbacks.
-  If you need to handle the same signal/event for multiple objects but
   differently (as in: different callbacks), include the name of the
   object in the callback name. Thus the event "``clicked``" for the
   ``Gtk.Button`` "``play_button``" would become "``on_play_button_clicked``".
   A small exception to this rule is when a word would be repeated.
   Thus "``on_play_button_press_event``" should be preferred over
   "``on_play_button_button_press_event``" for the "``button-press-event``"
   signal of the button.
-  If you use `Gtk.Builder <https://lazka.github.io/pgi-docs/Gtk-3.0/classes/Builder.html#Gtk.Builder>`_
   for UI descriptions, apply the rules above, make the callbacks methods
   of your class and simply call ``Gtk.Builder.connect_signals(self)``

Managed object access
---------------------

-  To keep classes interchangeable, try to make use of existing
   signals/events wherever possible. Avoid reaching deeply into property
   hierarchies under all circumstances. This is bound to break sooner
   than later.
-  If you need access to the main *exaile* object, call ``xl.main.exaile()``, if you need
   access to the main GUI object, call ``xlgui.get_controller()``, for the main window ``xlgui.main.mainwindow()``
-  Many systems are already ported to singleton managers. Examples are ``xl.covers``
   and ``xlgui.icons``. Simply use their ``MANAGER`` property to access them.

GUI
---

-  Use .ui files to define most widgets - reduces code clutter. A lot of
   basic structure can be easily prepared with the
   `Glade <https://glade.gnome.org/>`__ interface designer, especially
   objects where cell renderers and models are involved.
-  Try to avoid dialogs, as they are intrusive and users generally don't
   read them anyway. Inline alternatives like
   `Gtk.InfoBar <https://lazka.github.io/pgi-docs/Gtk-3.0/classes/InfoBar.html#Gtk.InfoBar>`__
   and its convenience wrapper ``xlgui.widgets.dialogs.MessageBar`` are much more effective.

Logging
-------

-  Messages should

   -  Be short but descriptive.
   -  Be proper English sentences, minus the period.
   -  Happen after the thing they are logging, UNLESS the thing might
      take a while, in which case it may be printed before, with a
      confirmation after the action completes.

      -  The tense of the message should match when it's sent - if after
         the action, use the past tense ("Logged into Audioscrobbler"),
         if before, use the present(?) tense ("Logging into
         audioscrobbler...").
      -  Messages which are present tense may use an ellipsis ("...") to
         indicate the different state more clearly than by tense alone.

   -  Not be given prefixes to identify module, as --debug will
      automatically add module names. It is acceptable to use related
      names in the message to increase clarity however. For example,
      "Logged into Audioscrobbler" is much clearer than "Logged in", but
      "Audioscrobbler: Logged in" is not acceptable.

-  There are 4 standard logging levels built into Exaile, their names
   and purpose are as follows:

   -  DEBUG - A significant internal event happened. Not shown by
      default.
   -  INFO - A major but expected event happened.
   -  WARNING - Something suboptimal happened. Exaile will continue to
      work properly but some features may be unavailable.
   -  ERROR - A critical error occurred. Exaile was unable to perform a
      requested action and may be in an inconsistent state if the error
      was not fully handled.

-  When writing messages, please run both with and without --debug to
   ensure it looks correct and does not duplicate the information
   provided by any other message.
-  Be sparing in the use of logging messages, particularly non-DEBUG
   messages. Logging messages are not an alternative to inserting print
   statements when debugging!

Other
-----

-  If you create a new on-disk format, add a version flag to it. This
   makes forwards and backwards compatibility MUCH easier should the
   format ever need to change.
