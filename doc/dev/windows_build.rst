.. _win32_installer:

Windows Installer
=================

.. note:: Windows installers are built by Appveyor automatically for every
          commit and pull request. Artifacts are currently retained for
          six months. You may find it easier to just download the installer
          from Appveyor instead of creating it yourself.
          
          Go to https://ci.appveyor.com/project/ExaileDevelopmentTeam/exaile/history,
          click a commit, and select 'Artifacts'.

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