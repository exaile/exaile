Frequently Asked Questions
==========================

Error "no suitable plugin found" when playing a (.mp3, .m4a, etc)
-----------------------------------------------------------------

Exaile 4.x currently uses GStreamer 1.x to decode/play audio files, and does not
directly decode audio itself. For playback to work, you need to have the
correct GStreamer plugins installed.

.. note:: For Linux users, you may find that other GStreamer programs can
          play a specific file type, but Exaile cannot. Check to make sure that
          the correct plugins are installed for GStreamer 1.x, as other
          players may be using GStreamer 0.10 instead.


File tags don't update when I change them using an external program
-------------------------------------------------------------------

When setting up your collection, ensure that the 'monitored' and 'scan on
startup' options are checked, otherwise Exaile may become out of sync with
your collection if it is modified by external programs.

To detect that the file has changed, Exaile checks to see if the
modification time of the file has changed. This makes rescans much
quicker.

Some third-party taggers (notably EasyTag) have options where they do not
update the modification time of the file when they change the contents of
the file. In these cases, Exaile may not be able to detect that the file
has changed. To remain compatible with Exaile (and other media players),
you should configure your tagger to update the modification time.

.. note:: As of Exaile 3.4.2, there is a menu option called 'Rescan Collection
          (slow)' which will force a rescan of every file in your collections,
          regardless of whether the modification time has changed. This should
          detect any changes to your collection.

How do I enable output to a secondary soundcard?
------------------------------------------------

**A**: Enable the 'preview device' plugin. You can change the secondary
output device settings by editing the plugin's settings.

Output switches to my primary output when I disconnect my secondary output?!
----------------------------------------------------------------------------

This issue occurs with some types of audio sinks that are available from
GStreamer. In particular, on many systems the PulseAudio system is configured
to automatically fallback to the another output if a stream is playing and its
output fails. Exaile's 'preview device' plugin has a hack that partially solves
this, but to truly solve it you have to convince your system to not do this.

On a system with PulseAudio, you must edit ``/etc/pulse/default.pa`` and
comment out the following line::

    load-module module-rescue-streams
