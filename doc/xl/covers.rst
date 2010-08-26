Cover
=====

.. automodule:: xl.covers

Cover Manager
*************

.. autodata:: MANAGER

.. autoclass:: CoverManager
    :members: find_covers,
              get_cover, set_cover, remove_cover,
              get_cover_data,
              get_default_cover,
              set_preferred_order,
              load, save

Cover Search Methods
********************

.. autoclass:: CoverSearchMethod
    :members: use_cache, name, find_covers, get_cover_data

.. autoclass:: TagCoverFetcher

.. autoclass:: LocalFileCoverFetcher
