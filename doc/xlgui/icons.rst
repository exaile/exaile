Icons & Images
==============

.. automodule:: xlgui.icons

Icon management
***************

.. data:: xlgui.icons.MANAGER

    Singleton instance of the :class:`IconManager`

.. autoclass:: IconManager
    :members: add_icon_name_from_directory,
              add_icon_name_from_file,
              add_icon_name_from_pixbuf,
              pixbuf_from_icon_name,
              pixbuf_from_rating

Utilities
*********

.. autoclass:: ExtendedPixbuf
    :members: add_horizontal, add_vertical,
              multiply_horizontal, multiply_vertical,
              composite_simple,
              move

.. autofunction:: extended_pixbuf_new_from_file
              
