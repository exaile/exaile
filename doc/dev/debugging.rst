
.. _debugging:

Debugging Exaile
================

.. contents::

What's an easy way to test stuff without wrecking my actual collection?
-----------------------------------------------------------------------

If you use the ``--all-data-dir`` option to Exaile, it will store all data
for that execution of Exaile in that directory (collections, playlists, logs):

.. code-block:: sh

    ./exaile --all-data-dir=tmp

Debugging options for Exaile
----------------------------

See ``--help`` for more details, but there are a few useful options:

* ``--debug`` - Shows debug log messages
* ``--eventdebug`` - Enable debugging of xl.event. Generates lots of output
* ``--eventdebug-full`` - Enable debugging of xl.event. Generates LOTS of output
* ``--threaddebug`` - Adds the thread name to logging messages

Where can I find log files?
---------------------------

On Linux/OSX:

* ``~/.local/share/exaile/logs/`` for Exaile 3.x releases

On Windows:

* ```%APPDATA%\..\Local\exaile``

Viewing stack traces when Exaile hangs
--------------------------------------

If you have the `faulthandler <https://github.com/haypo/faulthandler>`_ module
installed, on Linux/OSX if you send SIGUSR2 to Exaile it will dump stacktraces
of all current Python threads to stderr.
		
GStreamer Debugging Techniques
------------------------------

When tracking down GST issues, a useful thing to do is the following:

.. code-block:: sh

    $ GST_DEBUG=3 ./exaile
    $ GST_DEBUG="cat:5;cat2:3" .. etc. 

    $ GST_DEBUG="GST_STATES:4" ./exaile

``GST_DEBUG_NO_COLOR=1`` is good if you're running exaile inside of pydev on eclipse.

Additional help about GStreamer debugging variables can be found in its
`Documentation
<https://gstreamer.freedesktop.org/data/doc/gstreamer/head/gstreamer/html/gst-running.html>`_

GST Bin Visualization
~~~~~~~~~~~~~~~~~~~~~

This is pretty cool, shows you the entire GST pipeline:

.. code-block:: sh

    Gst.debug_bin_to_dot_file(some_gst_element, Gst.DebugGraphDetails.ALL, "filename")

Then if you run exaile like so:

.. code-block:: sh

    GST_DEBUG_DUMP_DOT_DIR=foo ./exaile 

It will dump a dot file that you can turn into an image:

.. code-block:: sh

    dot -Tpng -oimage.png graph_lowlevel.dot

Using GDB to diagnose issues
----------------------------

GDB can be used to diagnose segfaults and other issues. To run GDB:

.. code-block:: sh

    gdb --args python2 exaile.py --startgui <other arguments here>

Refer to the `Python Documentation <https://wiki.python.org/moin/DebuggingWithGdb>`_,
but especially useful here are:

* ``(gdb) py-bt`` is similar to ``(gdb) bt``, but it lists the python stack instead
* ``(gdb) info threads``

Tips for debugging issues related to Gtk+ or GLib
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Refer to the `Gtk+ <https://developer.gnome.org/gtk3/stable/gtk-running.html>`_
and `GLib <https://developer.gnome.org/glib/stable/glib-running.html>`_
debugging documentation.

Enable diagnostic warnings
~~~~~~~~~~~~~~~~~~~~~~~~~~

On GLib >= 2.46 you might want to set the ``G_ENABLE_DIAGNOSTIC`` environment
variable to show deprecation warnings. They are disabled by default since 2.46
and sometimes on older versions. See
`this commit <https://git.gnome.org/browse/glib/commit/gobject/gobject.c?id=3bd1618ea955f950f87bc4e452029c5f0cea35aa>`_.

Eliminating Gtk-WARNING
~~~~~~~~~~~~~~~~~~~~~~~

1. run gdb with ``G_DEBUG=fatal-warnings gdb --args python2 exaile --startgui``
2. run exaile from gdb with ``run``
3. do whatever causes `Gtk-WARNING`. This will lead to a crash in exaile.
4. debug this crash with gdb

**WARNING**: On Linux, this will freeze your X server if the crash
happens in a menu. This is due to `X grabbing all input on open menus
<https://tronche.com/gui/x/xlib/input/pointer-grabbing.html>`_.
When gdb stops exaile inside a menu it can't leave the input grab.

Prevent X server from freezing your Desktop when debugging exaile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some recommend starting exaile on another X server or on a Wayland backend. One
way to workaround this is to run exaile on a nested X server inside weston:

1. install weston
2. run ``weston --modules=xwayland.so`` (note: from now on all your Gtk+ 3.x applications will try to start inside weston due to preferring Wayland over X)
3. inside weston, run ``env | grep DISPLAY`` to figure out which X11 display to start exaile on
4. before running gdb, add ``GDK_BACKEND=x11` and `DISPLAY=:1`` (or whatever you got the step before) to its environment

To make Gtk+ 3.x applications not run inside weston but use your current X11
desktop session, run them with ``GDK_BACKEND=x11`` environment variable set.

Other thoughts
--------------

Exaile is written using Gtk+, GStreamer, and Python. Any generally useful
debugging tips that apply to those environments will often apply to Exaile also.
Quod Libet is another audio player uses Gtk/GStreamer and Python, their
development documentation also has useful debugging information:

* `Quod Libet Useful Development Tools <https://quodlibet.readthedocs.io/en/latest/development/tools.html>`_
