Frequently Asked Questions
==========================

Exaile doesn't update the file tags when I change them using an external program
---------------------------------------------------------------------------------

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

