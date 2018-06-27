
Release process
===============

This is an attempt to document what needs to be done in order to create a
release for Exaile.

Step one: Translations
----------------------

Ensure that the translations from `weblate <https://hosted.weblate.org/projects/exaile/master/>`_
are merged. Generally, this should happen automatically. It's probably easiest
to check via the command line in your repo.

If you haven't already, add weblate to your git remotes:

.. code-block:: sh

    $ git remote add weblate git://git.weblate.org/exaile.git

Check to see if the weblate repo has the same commits as the exaile
repo (assuming that origin is pointing at the main exaile repo).

.. code-block:: sh

    $ git fetch weblate
    $ git fetch origin
    $ git log -1 origin/master
    $ git log -1 weblate/master

If they're equivalent, then we're all set. If not, then figure out what needs
to be done to get them merged.

Step two: Version bumping
-------------------------

First, adjust the version in your local working tree to reflect the version
you want to make a release for. We should *never* do releases with -dev in
them.

The file to adjust is xl/version.py. You should do a commit, and then tag
the release.:

.. code-block:: sh

    $ git tag -a RELEASE_VERSION

Step three: Build the source distribution
-----------------------------------------

.. code-block:: sh

    $ make dist

.. _win32_installer:

Step four: Build the Windows installer
--------------------------------------

Install the SDK
~~~~~~~~~~~~~~~

You will need to have the SDK installed on your Windows machine. First clone
the repo somewhere.

.. code-block:: sh

    git clone https://github.com/exaile/python-gtk3-gst-sdk

Next install the SDK by running this from inside the tools/installer directory:

.. code-block:: sh

    /path/to/python-gtk3-gst-sdk/win_installer/build_win32_sdk.sh

Build the installer
~~~~~~~~~~~~~~~~~~~

Build the installer by running this command from the tools/installer directory:

.. code-block:: sh

    /path/to/python-gtk3-gst-sdk/win_installer/build_win32_installer.sh

.. _osx_installer:

Step five: OSX
--------------

This does not currently work, so we're not building releases for OSX at this
time.

Final steps
-----------

Upload everything to github:

* Linux: exaile-VERSION.tar.gz + exaile-VERSION.tar.gz.asc
* Windows: exaile-VERSION.exe + exaile-VERSION.exe.asc
* OSX: exaile-VERSION.dmg + exaile-VERSION.dmg.asc


Next, close out the milestone (if applicable) on github.

Next, bump the version again. The version in trunk should reflect the upcoming
release with a -dev in it.

TODO: Except after a beta/RC? What's the right transition?

Sending release notices
-----------------------

After a release, we should:

* Update website (hosted via github pages at https://github.com/exaile/exaile.github.io)

  - Update versions in ``_config.yml``
  - Add a new post to ``_posts``
 
* Send email to exaile-dev and exaile-users mailing lists
