
Exaile for OSX installation notes
=================================

Exaile has only been tested on OSX 10.8 Mountain Lion. It may work on
other versions of OSX, but they have not been tested. 

Requirements
============

Exaile requires the GStreamer SDK Runtime to be installed, otherwise it 
will not function. 

Download the SDK runtime for OSX here:

	http://docs.gstreamer.com/display/GstSDK/Installing+on+Mac+OS+X
	
Or use this direct download link:

	http://cdn.gstreamer.com/osx/universal/gstreamer-sdk-2013.6-universal.pkg

The default installation will allow the Exaile UI to work correctly, and 
should support playing many types of audio formats. 

However, by default GStreamer SDK does not install support for MP3 files or
certain other formats because of licensing issues. If you require support 
for these types of files, use the following procedure when installing 
GStreamer SDK.

- Run the GStreamer installation package
- Click continue
- Click "Agree" to agree to the license agreement
- Click "Install for all users of this computer", and click "Continue"
- Click "Customize"
- Ensure the following package names are checked:
	- GStreamer codecs under the GPL license
	- GStreamer restricted codecs 
	- GStreamer plugins for network protocols

- Click Install, and it should do the install for you
