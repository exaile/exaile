
Release process
===============

This is an attempt to document what needs to be done in order to create a
release for Exaile.

Step one: Translations
----------------------

Merge the translations from https://hosted.weblate.org/projects/exaile/master/

If you are a member of https://github.com/exaile you should be able to
import all translations from some github web UI into the git repository.

If you are not member clone git://git.weblate.org/exaile.git and add the
translations into your git repository.

Step two: Version bumping
-------------------------

First, adjust the version in your local working tree to reflect the version
you want to make a release for. We should *never* do releases with -dev in
them.

The file to adjust is xl/version.py. You should do a commit, and then tag
the release.:

.. code-block:: sh

    $ git tag RELEASE_VERSION


.. _win32_installer:

Step three: Installing the Python GTK3/GST SDK
----------------------------------------------

You will need to have the SDK installed. Here's what you do:

.. code-block:: sh

    git clone https://github.com/exaile/python-gtk3-gst-sdk

Next install the SDK links by running this from inside the tools/installer
directory, with the second argument set to the platform that you're building
for:

.. code-block:: sh

    /path/to/python-gtk3-gst-sdk/create_links.sh windows
    /path/to/python-gtk3-gst-sdk/create_links.sh osx


Step four: Building the Windows installer and source distribution
-----------------------------------------------------------------

You can build the source distribution and the Windows installer by running
the following:

.. code-block:: sh

    $ make dist
    

.. _osx_installer:

Step four: OSX
--------------

You can build the OSX DMG image by running the following from the
tools/installer directory:

.. code-block:: sh

    $ ./build_osx_installer.sh

If everything succeeded, you should find a file called "exaile-VERSION.dmg" at
tools/installer/exaile-VERSION.dmg.


Step five: Upload everything to github
--------------------------------------

* Linux: exaile-VERSION.tar.gz + exaile-VERSION.tar.gz.asc
* Windows: exaile-VERSION.exe + exaile-VERSION.exe.asc
* OSX: exaile-VERSION.dmg + exaile-VERSION.dmg.asc


Step six: close out the milestone on github
-------------------------------------------

TODO


Step seven: bump the version again
----------------------------------

The version in trunk should reflect the upcoming release with a -dev in it.

TODO: Except after a beta/RC? What's the right transition?

Step eight: send release notices
--------------------------------

* Update download links on exaile.org
* Add notice artifact to exaile.org
* Send email to mailing lists
