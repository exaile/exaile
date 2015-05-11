

Debugging tips
==============

TODO: developing with exaile

* Setup pydev properly
    * Add glib, gtk,pygst,gst,gobject to builtins
    * Add correct source directory
		
GST issues
----------

When tracking down GST issues, a useful thing to do is the following::

    $ GST_DEBUG=3 ./exaile
    $ GST_DEBUG="cat:5;cat2:3" .. etc. 

    $ GST_DEBUG="GST_STATES:4" ./exaile

`GST_DEBUG_NO_COLOR=1` is good if you're running exaile inside of pydev on eclipse.

Additional help about GStreamer debugging variables can be found at 
http://gstreamer.freedesktop.org/data/doc/gstreamer/head/manual/html/section-checklist-debug.html

GST Bin Visualization
---------------------

This is pretty cool, shows you the entire GST pipeline::

    gst.DEBUG_BIN_TO_DOT_FILE(some_gst_element, gst.DEBUG_GRAPH_SHOW_ALL, "filename")
    
Then if you run exaile like so::

    GST_DEBUG_DUMP_DOT_DIR=foo ./exaile 
    
It will dump a dot file that you can turn into an image::

    dot -Tpng -oimage.png graph_lowlevel.dot
