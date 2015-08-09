
#
# DANGER DANGER
#
# You must call Gst.init() before trying to use any GStreamer elements for
# anything. For example, if you import a module that has an object that
# inherits from Gst.Bin... that can potentially mess up any GStreamer object
# creation from that point forward.
#
# This means that Gst.init needs to be called before any plugins are loaded
#

from gi.repository import Gst
Gst.init(None)

import logging
logger = logging.getLogger(__name__)

logger.info("Using GStreamer %s.%s.%s", Gst.VERSION_MAJOR,
                                        Gst.VERSION_MINOR,
                                        Gst.VERSION_MICRO)

del logger
del logging

