
Getting Started
===============

You want to hack on Exaile? Rock on! The documentation for getting started isn't
as complete as we'd like (please help us improve it!), but this should help
you on your way:

Setting up a Development Environment
------------------------------------

Because Exaile is written in Python, if you can run Exaile on your machine,
then you can easily modify the source code and run that too. The Exaile
developers mostly run Exaile directly from the git checkout, without installing
Exaile:

.. code-block:: sh

    git clone https://github.com/exaile/exaile.git
    cd exaile
    # On Linux, Mac OS X or *BSD:
    ./exaile
    
    # On Windows:
    exaile.bat

If that works, then you're ready to go! If not, you need to install Exaile's
various dependencies:

Linux
~~~~~

On Ubuntu 16.04 following apt-get command should install most of the needed
dependencies:

.. code-block:: sh

    sudo apt-get install \
      python3-mutagen \
      python3-gi \
      python3-gi-cairo \
      python3-dbus \
      gir1.2-gtk-3.0 \
      gir1.2-gstreamer-1.0 \
      gir1.2-gst-plugins-base-1.0 \
      gstreamer1.0-plugins-base \
      gstreamer1.0-plugins-good \
      gstreamer1.0-plugins-ugly \
      gstreamer1.0-plugins-bad


Windows
~~~~~~~

First, install `msys2 <https://www.msys2.org/>`_. Then, open the MinGW32
shell window (look in the Start Menu for it), and run this monster (it may take
awhile):

.. code-block:: sh

  pacman -S \
    mingw-w64-i686-python3-gobject \
    mingw-w64-i686-python3-cairo \
    mingw-w64-i686-python3-pip \
    mingw-w64-i686-python3-bsddb3 \
    mingw-w64-i686-gtk3 \
    mingw-w64-i686-gdk-pixbuf2 \
    mingw-w64-i686-gstreamer \
    mingw-w64-i686-gst-plugins-base \
    mingw-w64-i686-gst-plugins-good \
    mingw-w64-i686-gst-plugins-bad \
    mingw-w64-i686-gst-libav \
    mingw-w64-i686-gst-plugins-ugly

Once that is complete, you'll want to install mutagen:

.. code-block:: sh

    python3 -m pip install mutagen

And then you should be able to launch Exaile from the msys2 console:

.. code-block:: sh

    cd exaile
    python3 exaile_win.py

OSX
~~~

The Python GTK3 GStreamer SDK repo can be used to install an appropriate
environment for OSX, and has instructions for setting it up:

* https://github.com/exaile/python-gtk3-gst-sdk/tree/master/osx_bundle

Other instructions
~~~~~~~~~~~~~~~~~~

See the `PyGObject Getting Started <https://pygobject.readthedocs.io/en/latest/getting_started.html>`_
documentation for getting the core PyGObject stuff installed. Once you get that
working, then you just need to use the appropriate package manager to install
GStreamer and things should be good to go.

Once you get pygobject working, you will also want to install mutagen via pip:

.. code-block:: sh

    python -m pip install mutagen

Useful documentation
--------------------

Exaile is built upon Python, PyGObject, Gtk+, and GStreamer. Here is a bunch of
documentation that you will find useful when working with these frameworks:

* `Python 3 <https://docs.python.org/3/>`_
* `PyGObject <https://pygobject.readthedocs.io>`_
* `Python GI API Reference <https://lazka.github.io/pgi-docs>`_
* `Python GTK+3 Tutorial <https://python-gtk-3-tutorial.readthedocs.io>`_
* `ABI/API tracker <https://abi-laboratory.pro/tracker/>`_ for tracking incompatible changes in C/C++ ABI and API

Useful tools
------------

* `Glade <https://glade.gnome.org/>`_ is what we use to edit the 'ui' xml files
  that describe our UI layout.
  
  .. warning:: Glade historically has been very prone to crashing, so when using
               it save your work often!

Editor setup
------------

Atom
~~~~

I've found recent versions of Github's Atom editor to be very useful for Python
development, I recommend installing the ``autocomplete-python`` and
``linter-pyflakes`` packages.

Eclipse + pydev
~~~~~~~~~~~~~~~

Pydev can be a bit tricky to set up correctly, see its documentation for details.

* Ensure you add the correct python interpreter in the project settings
* Add the root of the repository as a source directory

Running the tests
-----------------

If you have `pytest <https://docs.pytest.org>`_ installed, then you can just
run:

.. code-block:: sh

    make test
