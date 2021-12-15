
Release process
===============

This is an attempt to document what needs to be done in order to create a
release for Exaile.


Step 0: Upgrading the Exaile SDK for Windows (if needed)
--------------------------------------------------------

If you want to generate a new SDK, go to the `exaile-sdk-win project on AppVeyor
<https://ci.appveyor.com/project/ExaileDevelopmentTeam/exaile-sdk-win>`_
and click "New Build". Once the build is done, you can update the ``sdk_ver``
variable on ``appveyor.yml`` to the new SDK build number.

Note that new SDK versions can come with issues. It's better to do this step
well in advance and test the result to make sure nothing breaks. In fact it's
better to do this regularly, so that if something does break, we can revert to a
not-too-old SDK version.


Step 1: Translations
--------------------

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


Step 2: Gather and update release notes
---------------------------------------

There's a lot of ways to go about this. I find that the easiest way to see
what has changed is go to GitHub releases page, find the last release, and
click on XXX commits since this release. Then you can browse the list of
commits and pick out anything worth noting there.

If there is an actively-maintained changelog / release notes page, update it.
This may include updating the release date, preferably in UTC.


Step 3: Tag the release locally
-------------------------------

Make sure you have the correct thing checked out in your git tree, and then
tag the release.

.. code-block:: sh

    $ git tag -a RELEASE_VERSION

You can either add some release notes as the tag message or just write "Exaile
RELEASE_VERSION".


Step 4: Update plugin versions (if needed)
------------------------------------------

If the PLUGININFO files still refer to the old version number, update them:

.. code-block:: sh

    $ tools/plugin_tool.py fix

This currently must not be done from Windows because it will clobber the line
separators.

Note that the new version number in the PLUGININFO files does not include any
alpha/beta/rc label, so once you've done it for version a.b.c-alpha1 you don't
need to do this step again for version a.b.c.

Commit the changes and re-tag the release:

.. code-block:: sh

    $ git add plugins/*/PLUGININFO
    $ git commit
    $ git tag -d RELEASE_VERSION
    $ git tag -a RELEASE_VERSION


Step 5: Push the tag
--------------------

.. code-block:: sh

    $ git push origin RELEASE_VERSION

**Do not push to master** before doing this; our auto-release setup only works
when there is a new commit associated with a tag. If you've made this mistake,
delete the tag and create an empty commit:

.. code-block:: sh

    $ git tag -d RELEASE_VERSION
    $ git push -d origin RELEASE_VERSION
    $ git commit --allow-empty

then re-tag and re-push.


Step 6: Release the release
---------------------------

Once the tag is in the GitHub repository, GitHub Actions will build a source
tarball and AppVeyor will build a Windows installer.
They will create a draft release on GitHub containing those files.
Edit the draft, paste in your release notes, then click 'Publish Release'.

Ideally, the release notes should include a checksum for each release artifact.
This can be created (for the format we usually use) with

.. code-block:: sh

    sha256sum --tag FILENAME


Final steps
-----------

Once the tag is built and released, you can push to the master branch.

Next, close out the milestone (if applicable) on GitHub.


Sending release notices
-----------------------

After a release, we should:

* Update website (hosted via GitHub Pages at https://github.com/exaile/exaile.github.io)

  - Update versions in ``_config.yml``
  - Add a new post to ``_posts``

* Send email to exaile-dev and exaile-users mailing lists with the release notes
