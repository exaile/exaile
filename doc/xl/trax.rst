Trax
====

.. automodule:: xl.trax

Tracks
******

.. autoclass:: Track
    :members: list_tags, get_tag_sort, get_tag_display, get_tag_raw, set_tags, set_tag_raw, get_rating, set_rating, get_type, get_loc_for_io, local_file_name, set_loc, exists, read_tags, write_tags

.. autofunction:: is_valid_track

.. autofunction:: get_uris_from_tracks

.. autofunction:: get_tracks_from_uri

.. autofunction:: sort_tracks

.. autofunction:: sort_result_tracks

.. autofunction:: get_rating_from_tracks

Track Database
**************
Track databases are a simple persistence layer to hold collections of Track objects.

.. autoclass:: TrackDB
    :members: add, add_tracks, remove, remove_tracks, load_from_location, save_to_location


Searching
*********

.. autoclass:: TracksMatcher

.. autofunction:: search_tracks

.. autofunction:: search_tracks_from_string

