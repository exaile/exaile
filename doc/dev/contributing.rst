Contributing to Exaile
======================

The exaile team is always looking for others to help contribute to exaile
in various ways:

* Bugfixes
* Documentation updates
* New features + plugins
* Translations on https://hosted.weblate.org/engage/exaile/

The best way to contribute the first three is to submit patches via pull
request on GitHub.

If you think your bug report/request is being ignored, it probably isn't. All
of the Exaile developers work on this project in their spare time, and so we
don't always have time to work on specific problems. We *do* try to push good
patches as soon as we can, however. Ping the bug report, or leave a message on
#exaile if we haven't at least made an initial response, sometimes bug report
emails can get lost in the noise or forgotten.


Translating Exaile
------------------

Translations for Exaile should be done on `Exaile's Weblate project
<https://hosted.weblate.org/engage/exaile/>`_.
If you are new to Weblate, you may find the `Weblate translators guide
<https://docs.weblate.org/en/latest/user/index.html>`_ useful.


Python string formatting
~~~~~~~~~~~~~~~~~~~~~~~~

Python has two ways of specifying string formatting options.

**With %.** This method has several possible variations. Some examples:

* "Downloading %s" (a string)
* "Track number: %d" (an integer)
* "Size: %.2f MB" (a floating-point number, rounded to 2 decimal points)
* "Editing track %(current)d out of %(total)d" (two integers with
  disambiguating labels)

**With {}.** These are equivalent to the above examples:

* "Downloading {}"
* "Track number: {}"
* "Size: {:.2f} MB"
* "Editing track {current} out of {total}"

If you find two placeholders in one string with no labels to disambiguate them,
for example if you see "The %s has %d items" or "Loading: {} out of {}", please
report it as a bug.
This is because in some languages it may be necessary to reorder elements of
the string, which is impossible to do with both examples.


GTK+ keyboard mnemonics
~~~~~~~~~~~~~~~~~~~~~~~

An underscore (``_``) character in a GTK+ menu string indicates the keyboard
mnemonic for that menu item.
For example, the File menu is written as "_File" and the Open menu item is
written as "_Open", which then allows the user to access the File→Open menu
item by pressing ``Alt+F, O``.
You are encouraged to change these mnemonics to match existing conventions in
your language and to avoid conflicting mnemonics within the same menu.
