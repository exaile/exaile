# BCollection plugin for Exaile
The BCollection it's a plugin to Exaile and it aims to provide access to sqlite3 databases,
more precisely to databases of [Beets (The Music Geek's Media Organizer)](http://beets.io/), 
as-like the standard *Collection Panel*.

The plugin it's quite customizable and tries to reach an easy to comprehend interface with some over topics listed below.

## Beets Database
The database to Beets, it's a sqlite3 database, with a table called `Items`.

You can list the fields defined on it with: `beet fields`  

So, now we have defined the concept of field over this document, a field to beets or, more correct, a field to `Items` table.

Pre-defined fields:
    <br>&emsp; `count` - as `count(*)`
    <br>&emsp; `albumartists` - as `count(distinct albumartist)`
    <br>&emsp; `albums` - as `count(distinct albumartist||album)`
    <br>&emsp; `tracks` - as `count(distinct path)`
    <br>&emsp; `length` - as `sum(length)`, formatted in hours (e.g. 09:10:10)
    <br>&emsp; `bpm` - as `avg(bpm)`
    <br>&emsp; `added` and `mtime` - formatted as datetime (based on current locale)
    
## Tree View
Basically the Tree View (as each other) has the format:

    subgroup
      |- subgroup
        |- subgroup
          |- ...
          
Each subgroup is filtered by parent and it self, and go on...

This way, we have a syntax that divides it, with **%**:

    subgroup % subgroup % ... 

Each subgroup, define rules to sort, label and icon on Tree View's path, as, the text and icon for tooltip (of each subgroup), having the format:

    path & tooltip
    
Using **&** to separate it:

    subgroup 1 path & tooltip % subgroup 2 path & tooltip ...

Each subgroup can have a name, which is joined with ' - ', forming the names on *Select a view pattern* combo. 
    
    (:Artist) % (:Album) % (:Track)
    
    Artist - Album - Track

To output a field value, use:

    [field_name]
    
And it can have some format options from [Format String Syntax](https://docs.python.org/2/library/string.html#format-string-syntax),
basically the [format_spec](https://docs.python.org/2/library/string.html#grammar-token-format-spec).
    
    [day:02d]-[month:02d]-[year:04d]
   
And it also could have initial marks: 
    <br>&emsp; `*` - as icon
    <br>&emsp; `>` - in descendant order

    [>year:04d] [*album]

Well those defines fields to be showed on interface, but a field could be defined not to be showed, but to be used as sort.
It's the concept of hidden fields, and it's defined as:
    
    (disc)(track) 

It also accepts the same marks (icon and desc order), but do not uses the format_spec. 
Instead of that, for icons, it could define a size for it, as:

    (*album:52)
    
Attributes for that subgroup, the icon linked to `album` with 52 px. It could be used on path or tooltip.

Hidden fields also inserts another concept of field, an evaluated field, having the format:

    (?album:[album])
    (!album:Untitled album)

So, the concept is `?` for do have, and `!` for don't have, and all that comes after colon (`:`), is interpreted, if have or do not have value for field.

Use ` \ ` to escape chars.

A blank line separates patterns.

## Icons
Icons can be customized at preferences.

With Edit icons list, the name of icons used to each field can be changed.

The name must be a [valid gtk icon name](https://lazka.github.io/pgi-docs/index.html#Gtk-3.0/classes/Image.html#Gtk.Image.new_from_icon_name), or some icon defined by Exaile.

## Tips
* The auto-expand option at preferences, it's util for searches, so you could select the maximum rows to better fit your screen

* [Pango Text Attribute Markup Language](https://developer.gnome.org/pango/stable/PangoMarkupFormat.html) can be used to customize paths or tooltips, like:

    `<span foreground="blue">[album]</span>`
    
	`<b>Untitled</b>`
	
* Fonts are also customizable at preferences

* You can navigate on Tree View using arrow keys, plus, minus, divide and multiply keys, and also the initial letters, trying to find node that starts with the typed word

* `Ctrl` + `+` / `-` grows / compress letter size on Tree View

* `Ctrl` + `a` select all 

* Using `Shift` + `letter` will write it on search entry, grabbing focus

* Search entry accepts keys:
 
    `!` - NOT
    
    `|` - OR
    
    `~` - REGEXP
    
    `=` - `like` (values auto gets `%` at begin and end)
    
    `==` - explicit `like` operator (you must adds the `%` where you want)
    
    `()` - parentheses for precedence

* Searches are case insensitive and only use fields defined on current pattern (path/tooltip)

* Clearing the patterns (on preferences) restore the default view pattern

## Troubleshooting
If you think that any data are being showed duplicated on your tree view, look at items data, some of it may be different, as having a distinct `media` or any field that are listed on pattern, since fields are grouped on each level, any variation will generate a new row.

To fix it, you must fix data on Beets database (the sqlite3 database, blb) or you should avoid using this field, removing it from your path.
