
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

On Exaile 4, you can click the 'Open error logs' button in the 'Help' menu and
it will open the directory where logs are stored.

On Linux/OSX:

* ``~/.local/share/exaile/logs/`` for Exaile 3.x+ releases

On Windows:

* ``%APPDATA%\..\Local\exaile``

Viewing stack traces when Exaile hangs
--------------------------------------

On Linux/OSX if you send SIGUSR2 to Exaile it will dump stacktraces
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

Preparing GDB
~~~~~~~~~~~~~

Please make sure that you have installed debug symbols for all essential
non-python packages listed in :ref:`deps`. Python packages do not need debug
symbols, because they ship both binary and source files already. Depending on
the distribution you are using, you may obtain debug symbols in different ways.

* Fedora: Run ``dnf debuginfo-install [packagename]`` as root or with sudo.
  Fedora also ships a `C/C++ Debugger` with the Eclipse CDT (``eclipse-cdt``)
  package, which provides a useful GUI.
* Debian, Ubuntu, Linux Mint: Have a look at the wiki pages
  `Backtrace <https://wiki.ubuntu.com/Backtrace>`_ and
  `DebuggingProgramCrash <https://wiki.ubuntu.com/DebuggingProgramCrash#Installing_debug_symbols_manually>`_
* `Arch Linux <https://wiki.archlinux.org/index.php/Debug_-_Getting_Traces>`_

Basic Usage
~~~~~~~~~~~

GDB can be used to diagnose segfaults and other issues. To run GDB:

.. code-block:: sh

    gdb --args python3 exaile.py --startgui <other arguments here>

Refer to the `Python Documentation <https://wiki.python.org/moin/DebuggingWithGdb>`_,
but especially useful here are:

* ``(gdb) py-bt`` is similar to ``(gdb) bt``, but it lists the python stack instead
* ``(gdb) info threads``

Tips for debugging issues related to Gtk+ or GLib
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Refer to the `Gtk+ <https://developer.gnome.org/gtk3/stable/gtk-running.html>`_
and `GLib <https://developer.gnome.org/glib/stable/glib-running.html>`_
debugging documentation.

In particular, the GTK+ Inspector is very useful. On GTK 3.14+, hit CTRL-SHIFT-D
or CTRL-SHIFT-I to bring up GtkInspector to help debug UI problems. If the
hotkeys don't work, run Exaile with GTK_DEBUG=interactive. (On Gtk=3.18 this
sometimes causes GtkDialogs to crash on closing.)

Enable diagnostic warnings
~~~~~~~~~~~~~~~~~~~~~~~~~~

On GLib >= 2.46 you might want to set the ``G_ENABLE_DIAGNOSTIC`` environment
variable to show deprecation warnings. They are disabled by default since 2.46
and sometimes on older versions. See
`this commit <https://git.gnome.org/browse/glib/commit/gobject/gobject.c?id=3bd1618ea955f950f87bc4e452029c5f0cea35aa>`_.

Eliminating Gtk-WARNING
~~~~~~~~~~~~~~~~~~~~~~~

1. run gdb with ``G_DEBUG=fatal-warnings gdb --args python3 exaile --startgui``
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

Debugging segfaults (segmentation violations)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open a terminal.
2. Use the ``cd`` command to change to the directory where you put Exaile source
   code or to its installation directory.
3. Run ``gdb /usr/bin/python3``
4. In gdb, run ``set logging on exaile-segfault.txt`` to enable logging to that file.
5. In gdb, run ``run ./exaile.py --startgui``. You might append other arguments if you need them.
6. Use Exaile as you did before and try to reproduce the problem. At some point, exaile might freeze. This is when gdb caught the segmentation fault.
7. In gdb, run ``t a a py-bt`` and ``t a a bt full``. The first one will get python backtraces from all threads, the second one will get native (C/C++) stacktraces. You might need to type the return key a few times after each of these two commands to make gdb print all lines of the stack traces. This might take a while.
8. In gdb, type ``quit`` and press the enter key.
9. Please attach the file ``exaile-segfault.txt`` to a bug report at `Github <https://github.com/exaile/exaile/issues/new>`_ after you checked that it does not contain any private data. If you prefer to send the data encrypted, please feel free to encrypt them to the PGP key ID 0x545B42FB8713DA3B and send it to one of its Email addresses.

Debugging freezes
~~~~~~~~~~~~~~~~~

If Exaile freezes, follow the steps above for debugging segfaults but attach to the running instance instead.

1. Get the PID of Exaile. You may want to use ``top``, ``htop``, `KSysGuard` or `GNOME System Monitor` or a similar tool.
2. Follow the steps above, with one change: Instead of starting ``run ./exaile.py --startgui``, run the ``attach [pid]`` command inside gdb to attach to the exaile instance with the PID you retrieved in the previous step.

Debugging ignored exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes, especially when shutting down, Exaile may print a message like this:

    ``Exception TypeError: "'NoneType' object is not callable" in <object repr() failed> ignored``

You may see this output when the python runtime ran into an exception when calling `__del__` on an object or during garbage collection.
This output is generated by ``PyErr_WriteUnraisable`` in python's ``errors.c``. To debug it, attach gdb to Exaile or start Exaile in gdb and run ``break PyErr_WriteUnraisable``. Instead of writing the above message, gdb should break at the specified function and you should be able to get a backtrace.

Other thoughts
--------------

Exaile is written using Gtk+, GStreamer, and Python. Any generally useful
debugging tips that apply to those environments will often apply to Exaile also.
Quod Libet is another audio player uses Gtk/GStreamer and Python, their
development documentation also has useful debugging information:

* `Quod Libet Useful Development Tools <https://quodlibet.readthedocs.io/en/latest/development/tools.html>`_
