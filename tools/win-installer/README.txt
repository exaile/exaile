Building the Exaile installer
-----------------------------

Building the installer is currently only supported on Linux with wine installed.

Requirements
------------

First, download the python-gtk3-gst-sdk somewhere:

  git clone https://github.com/exaile/python-gtk3-gst-sdk
  
Next install the SDK links by running this from inside this directory:

  /path/to/python-gtk3-gst-sdk/create_links.sh windows

Building
--------

Just run 'make dist' from the main exaile directory.

Thanks
------

The Exaile NSIS installation script + SDK was heavily derived from the 
Quod Libet installation script + SDK: https://github.com/quodlibet/quodlibet

All installation scripts were released under the GPL, as is Exaile 

Dustin Spicuzza created the Exaile NSIS script

