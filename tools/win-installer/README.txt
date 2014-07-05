

Requirements for building installer
-----------------------------------
 
You can install these on Windows or Linux (if you have Wine installed).

* Install NSIS: http://nsis.sourceforge.net
* Install NSIS Inetc Plugin: http://nsis.sourceforge.net/Inetc_plug-in
    * Unzip it to ~/.wine/drive_c/Program Files (x86)/NSIS
    * Or on windows, to C:\Program Files\NSIS 

Usage (Linux)
-------------

Just run 'make dist' from the main exaile directory.

Usage (Windows)
---------------

From Exaile main directory:
- bzr export dist/copy
- run NSIS installer on exaile_installer.nsi
    - I just right click on it and select 'Compile NSIS Script'

And that's about it. Should create an exe called exaile-LATEST.exe and it
should 'just work'.


Thanks
------

The Exaile NSIS installation script was originally heavily derived from the 
Quod Libet installation script: http://code.google.com/p/quodlibet/

However, the ASCEND project (http://www.ascend4.org/) had a lot of really 
cool stuff to download and install dependencies, and so a lot was borrowed 
from them too. Dependencies.nsi, detect.nsi, and download.nsi are originally
derived from their NSIS installer.

All installation scripts were released under the GPL, as is Exaile 

Dustin Spicuzza created the Exaile NSIS script

