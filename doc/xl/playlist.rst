Playlist
========

.. automodule:: xl.playlist

Playlists
*********

.. autoclass:: Playlist
    :members: name, current_position, spat_position, dirty,
              shuffle_modes, shuffle_mode_names,
              shuffle_mode, repeat_mode, dynamic_mode,
              append, extend, count, index, pop, clear,
              get_current_position, set_current_position,
              get_spat_position, set_spat_position,
              get_current,
              get_shuffle_history, clear_shuffle_history,
              next, prev,
              get_shuffle_mode, set_shuffle_mode,
              get_repeat_mode, set_repeat_mode,
              get_dynamic_mode, set_dynamic_mode,
              randomize, sort,
              save_to_location, load_from_location


Playlist Converters
*******************

.. autoclass:: FormatConverter
    :members: export_to_file, import_from_file,
              name_from_path

.. autoclass:: M3UConverter
    :show-inheritance:

.. autoclass:: PLSConverter
    :show-inheritance:

.. autoclass:: ASXConverter
    :show-inheritance:

.. autoclass:: XSPFConverter
    :show-inheritance:
