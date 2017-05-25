==========================================
 spydaap: a simple DAAP server for python
==========================================

spydaap is a Digital Audio Access Protocol (DAAP) server -- DAAP is the 
protocol used by Apple's iTunes software.  Running spydaap on your machine
allows any DAAP enabled music player to browse and play selections from your
music collection (including music players running on the same machine as the
server).  There are several DAAP capable players available for all major
operating systems.

Because iTunes 7.0 and newer do not enable music to be shared with any other
kinds of DAAP clients, it is recommended that OS X users run spydaap on their
machines, which will allow any DAAP client to connect to it (including old and
new versions of iTunes).

Requirements
------------

1. Python 2.5 or later
2. `mutagen <http://code.google.com/p/mutagen/>`_
3. `pybonjour <http://code.google.com/p/pybonjour/>`_ or python-avahi


Running without installing
--------------------------

From outside this directory, simply run::

    $ python <name of directory containing __main__.py>

It is also possible to create a zipped version of this directory (a so-called
'python egg' -- often the extension of this zipfile is chosen to be 'egg').  In
this case, run::

    $ python <name of zipped file>

From inside this directory, run::

    $ python run_spydaap


Installing
----------

Ubuntu/Debian
~~~~~~~~~~~~~

::

  $ sudo apt-get install python-mutagen python-avahi
  $ cd spydaap
  $ sudo python setup.py install

Mac OS X
~~~~~~~~

spydaap requires a version of Python later than 2.3. If you are
running Mac OS 10.4 or earlier, you will need to install a more recent
version of Python and setuptools.

::

  $ cd spydaap
  $ sudo python setup.py install

Running
-------

::

  $ spydaap

``~/Music/`` is the default directory where spydaap looks for media
files. It can be changed by editing ``~/.spydaap/config.py`` (see
``config.py.example``)

Customizing
-----------

See ``config.py.example`` for information on setting port, name,
etc. There also examples of some custom smart playlists. For writing
your own smart playlists, see ``spydaap/playlists.py``.
