
Release process
===============

This is an attempt to document what needs to be done in order to create a
release for Exaile.

Step one: Translations
----------------------

Merge the translations branch for the current series.

If a new series was created and no translations branch exists, follow
these steps:

* Create a new branch for translations, include the series in the branch
  name, like "translations-3.4.x" for the "3.4.x" series
* Open the translation settings page of the series on Launchpad:
  https://translations.launchpad.net/exaile/3.4.x/+translations-settings
* In "Import translations from branch" you should at least select
  "Import template files" to have changes in code automatically show up
  in the translation tool of Launchpad.
* In "Export translations to branch" you just "Choose a target branch",
  namely the one you just created.

You can reach the settings for all series via the general translations
page: https://translations.launchpad.net/exaile

Step two: Version bumping
-------------------------

First, adjust the version in your local working tree to reflect the version
you want to make a release for. We should *never* do releases with -dev in
them.

The file to adjust is xl/version.py. You should do a commit, and then tag
the release.::

    $ bzr tag RELEASE_VERSION


.. _win32_installer:

Step three: Linux + Windows
---------------------------

The 'make dist' command will build both the source distribution and the
Windows version using NSIS running on Wine. You must install NSIS and the
inetc plugin.

* Install NSIS 2 (http://nsis.sourceforge.net/Main_Page)
* Install the inetc plugin (http://nsis.sourceforge.net/Inetc_plug-in)
    * Unzip it to `~/.wine/drive_c/Program Files (x86)/NSIS`

Once everything is installed, you can just run the following::

    $ make dist
    

.. _osx_installer:

Step four: OSX
--------------

You need py2app installed to create an OSX dmg file. Once you have that
installed, then you can do the following::

    $ cd tools/osx
    $ ./create_dmg.sh

If everything succeeded, you should find a file called "exaile-VERSION.dmg" at
dist/exaile-VERSION.dmg.


Step five: Upload everything to launchpad
-----------------------------------------

* Linux: exaile-VERSION.tar.gz + exaile-VERSION.tar.gz.asc
* Windows: exaile-VERSION.exe + exaile-VERSION.exe.asc
* OSX: exaile-VERSION.dmg + exaile-VERSION.dmg.asc


Step five: clean any relevant bug reports
-----------------------------------------

Next, any bugs on launchpad for the release should be marked as 'Fix released'. There is
an easy way to do this via email...  TODO


Step six: bump the version again
--------------------------------

The version in trunk should reflect the upcoming release with a -dev in it.

TODO: Except after a beta/RC? What's the right transition?

Step seven: send release notices
--------------------------------

* Update download links on exaile.org
* Add article to exaile.org
* Send email to mailing lists
