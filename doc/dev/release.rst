
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

Step two: gather release notes
------------------------------

There's a lot of ways to go about this. I find that the easiest way to see
what has changed is go to github releases page, find the last release, and
click on XXX commits since this release. Then you can browse the list of
commits and pick out anything worth noting there.

Step three: Tag the release
---------------------------

Make sure you have the correct thing checked out in your git tree, and then
tag the release. 

.. code-block:: sh

    $ git tag -a RELEASE_VERSION

You'll want to paste in the release notes into the tag message. Then, push
the tag to github:

.. code-block:: sh

    $ git push origin RELEASE_VERSION

Step four: Release the release
------------------------------

Once the tag is in github, Travis-CI will build a Linux dist and Appveyor
will build a Windows installer and upload it to Github releases as a draft.
Once the assets are uploaded, you can edit the draft release and paste in
your release notes, then click 'Publish Release'.

Final steps
-----------

Next, close out the milestone (if applicable) on github.

Sending release notices
-----------------------

After a release, we should:

* Update website (hosted via github pages at https://github.com/exaile/exaile.github.io)

  - Update versions in ``_config.yml``
  - Add a new post to ``_posts``
 
* Send email to exaile-dev and exaile-users mailing lists with the release notes
