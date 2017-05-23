Exaile Installers
-----------------

Only a source distribution is provided for Linux platforms.

Building the Windows installer is currently only supported on Linux with
wine installed, but it also seems to work on OSX.

Building the OSX installer is only possible on OSX at this time.

Requirements
------------

First, download the python-gtk3-gst-sdk somewhere:

  git clone https://github.com/exaile/python-gtk3-gst-sdk

Next install the SDK links by running this from inside this directory:

  /path/to/python-gtk3-gst-sdk/create_links.sh windows
  /path/to/python-gtk3-gst-sdk/create_links.sh osx

Building Windows installer
--------------------------

Just run /path/to/python-gtk3-gst-sdk/win_installer/build_win32_installer.sh

Building OSX DMG image
----------------------

Just run `./build_osx_installer.sh` from this directory.

Thanks
------

The Exaile NSIS installation script + SDK was heavily derived from the
Quod Libet installation script + SDK: https://github.com/quodlibet/quodlibet

All installation scripts were released under the GPL, as is Exaile
