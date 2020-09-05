# Copyright (C) 2012 Mathias Brodala
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


from collections import namedtuple
import logging
import sys

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from xl import event, player, settings as xl_settings
from xl.nls import gettext as _
from xlgui.widgets import info
from xlgui import guiutil

from . import osd_preferences


LOGGER = logging.getLogger(__name__)


Point = namedtuple('Point', 'x y')


def do_assert(is_bool):
    """
    Simulates the `assert` statement
    """
    if not is_bool:
        raise AssertionError()


def _sanitize_window_geometry(
    window, current_allocation, padding, width_fill, height_fill
):
    """
    Sanitizes (x-offset, y-offset, width, height) of the given window,
    to make the window show on the screen.

    :param width_fill, height_fill: specifies the maximum width or height
        of a monitor to fill. 1.0 means "fill the whole monitor"
    :param padding: specifies the padding (from workarea border) to leave empty
    """
    work_area = guiutil.get_workarea_dimensions(window)
    cural = current_allocation
    newal = Gdk.Rectangle()

    newal.x = max(padding, cural.x)
    newal.y = max(padding, cural.y)

    newal.width = min(work_area.width // width_fill, cural.width)
    newal.height = min(work_area.height // height_fill, cural.height)

    newal.x = min(newal.x, work_area.x + work_area.width - newal.width - padding)
    newal.y = min(newal.y, work_area.y + work_area.height - newal.height - padding)

    if newal == cural:
        return None

    if cural.x != newal.x or cural.y != newal.y:
        if cural.width != newal.width or cural.height != newal.height:
            window.get_window().move_resize(newal.x, newal.y, newal.width, newal.height)
        else:
            window.move(newal.x, newal.y)
    else:
        if cural.width != newal.width or cural.height != newal.height:
            window.resize(newal.width, newal.height)
    return newal


class OSDPlugin:
    """
    The plugin for showing an On-Screen Display.
    This object holds all the stuff which may live longer than the window.
    Please note that the window has to be destroyed during plugin runtime,
    see the OSDWindow docstring below for details.
    """

    __window = None
    __css_provider = None
    __options = None

    def enable(self, _exaile):
        """
        Enables the on screen display plugin
        """
        do_assert(self.__window is None)

        # Note: Moving windows will not work on Wayland by design, because Wayland does not know
        # absolute window positioning. Gtk.Window.move() does not work there.
        # See https://blog.gtk.org/2016/07/15/future-of-relative-window-positioning/
        # and https://lists.freedesktop.org/archives/wayland-devel/2015-September/024464.html
        if guiutil.platform_is_wayland():
            raise EnvironmentError("This plugin does not work on Wayland backend.")

        # Cached option values
        self.__options = {
            'background': None,
            'display_duration': None,
            'border_radius': None,
            'use_alpha': False,
        }
        self.__css_provider = Gtk.CssProvider()
        if sys.platform.startswith("win32"):
            # Setting opacity on Windows crashes with segfault,
            # see https://bugzilla.gnome.org/show_bug.cgi?id=674449
            self.__options['use_alpha'] = False
            LOGGER.warning(
                "OSD: Disabling alpha channel because it is not supported on Windows."
            )
        else:
            self.__options['use_alpha'] = True

    def teardown(self, _exaile):
        """
        Shuts down the on screen display plugin
        """
        do_assert(self.__window is not None)
        self.__window.destroy_osd()
        event.remove_callback(self.__on_option_set, 'plugin_osd_option_set')
        event.remove_callback(self.__on_playback_track_start, 'playback_track_start')
        event.remove_callback(self.__on_playback_toggle_pause, 'playback_toggle_pause')
        event.remove_callback(self.__on_playback_player_end, 'playback_player_end')
        event.remove_callback(self.__on_playback_error, 'playback_error')
        self.__window = None

    def disable(self, _exaile):
        """
        Disables the on screen display plugin
        """
        self.teardown(_exaile)

    def on_gui_loaded(self):
        """
        Called when Exaile mostly finished loading
        """
        do_assert(self.__window is None)
        event.add_callback(self.__on_option_set, 'plugin_osd_option_set')
        self.__prepare_osd(False)
        # TODO: OSD looks ugly with CSS not applied on first show. Why is that?

        event.add_callback(self.__on_playback_track_start, 'playback_track_start')
        event.add_callback(self.__on_playback_toggle_pause, 'playback_toggle_pause')
        event.add_callback(self.__on_playback_player_end, 'playback_player_end')
        event.add_callback(self.__on_playback_error, 'playback_error')

    def get_preferences_pane(self):
        """
        Called when the user wants to see the preferences pane for this plugin
        """
        osd_preferences.OSDPLUGIN = self
        return osd_preferences

    def make_osd_editable(self, be_editable):
        """
        Rebuilds the OSD to make it movable and resizable
        """
        do_assert(self.__window is not None)
        self.__window.destroy_osd()
        self.__window = None
        self.__prepare_osd(be_editable)
        self.__window.show_for_a_while()

    def __prepare_osd(self, be_editable):
        do_assert(self.__window is None)
        self.__window = OSDWindow(self.__css_provider, self.__options, be_editable)
        # Trigger initial setup through options.
        for option in (
            'format',
            'background',
            'display_duration',
            'show_progress',
            'position',
            'width',
            'height',
            'border_radius',
        ):
            self.__on_option_set(
                'plugin_osd_option_set',
                xl_settings,
                'plugin/osd/{option}'.format(option=option),
            )
        self.__window.restore_geometry_and_show()

    def __on_option_set(self, _event, settings, option):
        """
        Updates appearance on setting change
        """
        if option == 'plugin/osd/format':
            self.__window.info_area.set_info_format(
                settings.get_option(option, osd_preferences.FormatPreference.default)
            )
        elif option == 'plugin/osd/background':
            if not self.__options['background']:
                self.__options['background'] = Gdk.RGBA()
            rgba = self.__options['background']
            rgba.parse(
                settings.get_option(
                    option, osd_preferences.BackgroundPreference.default
                )
            )
            if self.__options['use_alpha'] is True:
                if rgba.alpha > 0.995:
                    # Bug: We need to set opacity to some value < 1 here
                    # otherwise both corners and fade out transition will look ugly
                    rgba.alpha = 0.99
                    settings.set_option(option, rgba.to_string())
            else:
                if rgba.alpha < 1:
                    rgba.to_color()
                    settings.set_option(option, rgba.to_string())
            GLib.idle_add(self.__update_css_provider)
        elif option == 'plugin/osd/border_radius':
            value = settings.get_option(
                option, osd_preferences.BorderRadiusPreference.default
            )
            self.__window.set_border_width(max(6, value // 2))
            self.__options['border_radius'] = value
            GLib.idle_add(self.__update_css_provider)
            self.__window.emit('size-allocate', self.__window.get_allocation())
        elif option == 'plugin/osd/display_duration':
            self.__options['display_duration'] = int(
                settings.get_option(
                    option, osd_preferences.DisplayDurationPreference.default
                )
            )
        elif option == 'plugin/osd/show_progress':
            self.__window.info_area.set_display_progress(
                settings.get_option(
                    option, osd_preferences.ShowProgressPreference.default
                )
            )
        elif option == 'plugin/osd/position':
            position = Point._make(settings.get_option(option, [20, 20]))
            self.__window.geometry['x'] = position.x
            self.__window.geometry['y'] = position.y
        elif option == 'plugin/osd/width':
            width = settings.get_option(option, 300)
            self.__window.geometry['width'] = width
        elif option == 'plugin/osd/height':
            height = settings.get_option(option, 120)
            self.__window.geometry['height'] = height

    def __update_css_provider(self):
        bgcolor = self.__options['background']
        radius = self.__options['border_radius']
        if bgcolor is None or radius is None:
            return  # seems like we are in early initialization state
        if self.__options['use_alpha'] is True:
            color_str = guiutil.css_from_rgba(bgcolor)
        else:
            color_str = guiutil.css_from_rgba_without_alpha(bgcolor)
        data_str = "window { background-color: %s; border-radius: %spx; }" % (
            color_str,
            str(radius),
        )
        self.__css_provider.load_from_data(data_str.encode('utf-8'))
        return False

    def __on_playback_track_start(self, _event, _player, _track):
        self.__window.show_for_a_while()

    def __on_playback_toggle_pause(self, _event, _player, _track):
        self.__window.show_for_a_while()

    def __on_playback_player_end(self, _event, _player, track):
        if track is None:
            self.__window.hide_immediately()
        else:
            self.__window.show_for_a_while()

    def __on_playback_error(self, _event, _player, _message):
        # TODO: show error instead?
        self.__window.hide_immediately()


plugin_class = OSDPlugin


class OSDWindow(Gtk.Window):
    """
    A popup window showing information of the currently playing track

    Due to the way, the Gtk+ API and some of the many different window managers work,
    the OSD cannot be resizable and movable and have no keyboard focus nor decorations
    at the same time.
    Additionally, in some cases the Gtk+ API specifies that functions may not
    be called after the window has been realized (). In some other cases, Gtk+ API does
    not guarantee that a function works after Gtk.Window.show() is called
    (e.g. Gtk.Window.set_decorated(), set_deletable(), set_titlebar()).
    For these reasons, we need to destroy and rebuild the OSD when we want it to be
    resizable and movable by simple drag operations.

    Another related bug report:
    https://bugzilla.gnome.org/show_bug.cgi?id=782117:
         If a window was initially shown undecorated and set_decorated(True) is called,
         titlebar is drawn inside the window
    """

    __hide_id = None
    __fadeout_id = None
    __autohide = True
    __options = None
    geometry = dict(x=20, y=20, width=300, height=120)  # the default

    def __init__(self, css_provider, options, allow_resize_move):
        """
        Initializes the OSD Window.
        Important: Do not call this constructor before Exaile finished loading,
            otherwise the internal TrackInfoPane will re-render label and icon on each
            `track_tags_changed` event, which causes unnecessary CPU load and delays startup.

        Apply the options after this object was initialized.
        """
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.__options = options

        self.set_title('Exaile OSD')
        self.set_keep_above(True)
        self.stick()

        # the next two options don't work on GNOME/Wayland due to a bug
        # between Gtk+ and gnome-shell:
        # https://bugzilla.gnome.org/show_bug.cgi?id=771329
        # there is no API guaranty that they work on other platforms.
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        # There is no API guaranty that set_deletable() will work
        self.set_deletable(False)
        self.connect('delete-event', lambda _widget, _event: self.hide_immediately)

        self.connect('screen-changed', self.__on_screen_changed)

        style_context = self.get_style_context()
        style_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Init child widgets
        self.info_area = info.TrackInfoPane(player.PLAYER)
        self.info_area.set_default_text(_('No track played yet'))
        # enable updating OSD contents
        # this is very expensive if done during Exaile startup!
        self.info_area.set_auto_update(True)
        self.info_area.cover.set_property('visible', True)
        # If we don't do this, the label text will be selected if the user
        # pressed the mouse button while the OSD is shown for the first time.
        self.info_area.info_label.set_selectable(False)
        self.info_area.show_all()
        self.add(self.info_area)

        self.__setup_resize_move_related_stuff(allow_resize_move)

        # callbacks needed to show the OSD long enough:
        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect('leave-notify-event', self.__on_leave_notify_event)

        # Also, maximize, minimize, etc. might happen and we want to undo that
        self.add_events(Gdk.EventMask.STRUCTURE_MASK)
        self.connect('window-state-event', self.__on_window_state_event)

        # Needed to acquire size
        self.info_area.set_display_progress(True)

        # set up the window visual
        self.__on_screen_changed(self, None)

    def __setup_resize_move_related_stuff(self, allow_resize_move):
        # Without decorations, the window cannot be resized on some desktops
        # this especially effects GNOME/Wayland and is probably caused by
        # missing client-side decorations (CSD). This code might break when
        # using client side decorations. In this case, we probably shoud hide
        # the titlebar instead of removing the decorations.
        # Removing decorations is ignored on some platforms to enable
        # the resize grid.
        self.set_decorated(False)
        self.set_resizable(allow_resize_move)

        if allow_resize_move:
            self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            self.set_title(_("Move or resize OSD"))
            # This is often ignored, but we could try:
            self.connect(
                'realize',
                lambda _widget: self.get_window().set_decorations(
                    Gdk.WMDecoration.RESIZEH | Gdk.WMDecoration.TITLE
                ),
            )
        else:
            # On X11 (at least XWayland), this will make the window be not movable,
            # but makes sure the user can still type.
            self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)

        # We do not want to disturb user keyboard input
        self.set_accept_focus(allow_resize_move)

        self.__autohide = not allow_resize_move

    def __on_window_state_event(self, _widget, win_state):
        illegal_states = (
            Gdk.WindowState.FULLSCREEN
            | Gdk.WindowState.ICONIFIED
            | Gdk.WindowState.TILED
            | Gdk.WindowState.MAXIMIZED
            | Gdk.WindowState.BELOW
        )
        if (
            win_state.changed_mask & illegal_states
            and win_state.new_window_state & illegal_states
        ):
            # Just returning Gdk.EVENT_STOP doesn't stop the window manager
            # from changing window state.
            # TODO: This often does not work at all.
            GLib.idle_add(self.restore_geometry_and_show)
            return Gdk.EVENT_STOP
        else:
            return Gdk.EVENT_PROPAGATE

    def destroy_osd(self):
        """
        Cleanups
        """
        # Getting the position can only work on a window being shown on screen
        # This is no problem since the window will be shown permanently during configuration.
        if self.is_visible():
            # X11: Position is off by OSD, because it is fetched with OSD but set without OSD
            #    There is no simple way to fix this because we don't know the OSD geometry.
            # Wayland: Position does not work at all.
            xl_settings.set_option('plugin/osd/position', list(self.get_position()))

            # Don't use Gdk.Window.get_width() here, it may include client-side window decorations!
            # This is not guaranteed to work according to Gtk.Window docs, but it works for me.
            width, height = self.get_size()
            xl_settings.set_option('plugin/osd/width', width)
            xl_settings.set_option('plugin/osd/height', height)
        self.hide_immediately()
        if self.__fadeout_id:
            GLib.source_remove(self.__fadeout_id)
            self.__fadeout_id = None
        if self.__hide_id:
            GLib.source_remove(self.__hide_id)
            self.__hide_id = None
        Gtk.Window.destroy(self)

    def __start_fadeout(self):
        """
        Starts fadeout of the window.
        Hides the window it immediately if fadeout is disabled
        """
        self.__hide_id = None

        gdk_display = self.get_window().get_display()
        # Keep showing the OSD in case the pointer is still over the OSD
        if (
            Gtk.get_major_version() > 3
            or Gtk.get_major_version() == 3
            and Gtk.get_minor_version() >= 20
        ):
            gdk_seat = gdk_display.get_default_seat()
            gdk_device = gdk_seat.get_pointer()
        else:
            gdk_device_manager = gdk_display.get_device_manager()
            gdk_device = gdk_device_manager.get_client_pointer()
        window, _posx, _posy = gdk_device.get_window_at_position()
        if window and window is self.get_window():
            self.show_for_a_while()
            return

        if self.__options['use_alpha'] is True:
            if self.__fadeout_id is None:
                self.__fadeout_id = GLib.timeout_add(30, self.__do_fadeout_step)
        else:
            Gtk.Window.hide(self)
        return False

    def show_for_a_while(self):
        """
        This method makes sure that the OSD is shown. Any previous hiding
        timers or fading transitions will be stopped.
        If hiding is allowed through self.__autohide, a new hiding timer
        will be started.
        """
        # unset potential fadeout process
        if self.__fadeout_id:
            GLib.source_remove(self.__fadeout_id)
            self.__fadeout_id = None
        if Gtk.Widget.get_opacity(self) < 1:
            Gtk.Widget.set_opacity(self, 1)
        # unset potential hide process
        if self.__hide_id:
            do_assert(self.__fadeout_id is None)
            GLib.source_remove(self.__hide_id)
            self.__hide_id = None
        # (re)start hide process
        if self.__autohide:
            self.__hide_id = GLib.timeout_add_seconds(
                self.__options['display_duration'], self.__start_fadeout
            )
        Gtk.Window.present(self)

    def restore_geometry_and_show(self):
        """
        Restores window geometry from options and shows the window afterwards.
        """
        geo = self.geometry
        # automatically resizes to minimum required size
        self.set_default_size(geo['width'], geo['height'])

        self.move(geo['x'], geo['y'])
        self.show_for_a_while()
        # screen size might have changed
        allocation = Gdk.Rectangle()
        allocation.x = geo['x']
        allocation.y = geo['y']
        allocation.width = geo['width']
        allocation.height = geo['height']
        _sanitize_window_geometry(super(Gtk.Window, self), allocation, 10, 0.2, 0.2)

    def set_autohide(self, do_autohide):
        """
        Permanently shows the OSD during configuration.
        This method should only be used from osd_preferences.
        """
        self.__autohide = do_autohide
        if do_autohide:
            do_assert(self.__hide_id is None)
            do_assert(self.__fadeout_id is None)
        GLib.idle_add(self.show_for_a_while)

    def __do_fadeout_step(self):
        """
        Constantly decreases the opacity to fade out the window
        """
        do_assert(self.__hide_id is None)
        if Gtk.Widget.get_opacity(self) > 0.001:
            Gtk.Widget.set_opacity(self, Gtk.Widget.get_opacity(self) - 0.05)
            return True
        else:
            self.__fadeout_id = None
            Gtk.Window.hide(self)
            return False

    def __on_screen_changed(self, _widget, _oldscreen):
        """
        Updates the used colormap
        """
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            # This might happen if there is no X compositor so the X Server
            # does not support transparency
            visual = screen.get_system_visual()
            self.__options['use_alpha'] = False
            LOGGER.warning(
                "OSD: Disabling alpha channel because the Gtk+ "
                "backend does not support it."
            )
        self.set_visual(visual)

    '''
    def __on_size_allocate(self, _widget, _allocation):
        """
            Applies the non-rectangular shape
        """
        # TODO: make this work again
        # Bug in pycairo: cairo_region_* functions are not available before
        # version 1.11.0, see https://bugs.freedesktop.org/show_bug.cgi?id=44336
        # we might want to enable this code below once pycairo is distributed on
        # most Linux distros.
        # cairo_region = cairo.Region.create_rectangle(allocation)
        # as a result, calling
        # self.get_window().shape_combine_region(cairo_region, 0, 0)
        # is impossible. Thus, it is impossible to shape the window.
        # Instead, we have to work around this issue by leaving parts
        # of the window undrawn.

        # leave the old code here for reference:
        width, height = allocation.width, allocation.height
        mask = Gdk.Pixmap(None, width, height, 1)
        context = mask.cairo_create()

        context.set_source_rgb(0, 0, 0)
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()

        radius = self.__options['border_radius']
        inner = (radius, radius, width - radius, height - radius)

        context.set_source_rgb(1, 1, 1)
        context.set_operator(cairo.OPERATOR_SOURCE)
        # Top left corner
        context.arc(inner.x,     inner.y,      radius, 1.0 * pi, 1.5 * pi)
        # Top right corner
        context.arc(inner.width, inner.y,      radius, 1.5 * pi, 2.0 * pi)
        # Bottom right corner
        context.arc(inner.width, inner.height, radius, 0.0 * pi, 0.5 * pi)
        # Bottom left corner
        context.arc(inner.x,     inner.height, radius, 0.5 * pi, 1.0 * pi)
        context.fill()

        self.shape_combine_mask(mask, 0, 0)
    '''

    def __on_leave_notify_event(self, _widget, event_crossing):
        # NotifyType.NONLINEAR means the pointer left the window, not just the widget.
        if event_crossing.detail == Gdk.NotifyType.NONLINEAR:
            self.show_for_a_while()
        return Gdk.EVENT_PROPAGATE

    def hide_immediately(self):
        """
        Immediately hides the OSD and removes all remaining timers or transitions
        """
        if self.__fadeout_id:
            GLib.source_remove(self.__fadeout_id)
            self.__fadeout_id = None
        if self.__hide_id:
            GLib.source_remove(self.__hide_id)
            self.__hide_id = None
        Gtk.Window.hide(self)
