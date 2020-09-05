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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.
"""
This module serves as frontend for GStreamer Plugin Base Utils (GstPbutils) for
installing missing plugins.

See also:
* https://github.com/quodlibet/quodlibet/blob/master/quodlibet/quodlibet/player/gstbe/player.py#L548
* https://git.gnome.org/browse/totem/tree/src/backend/bacon-video-widget-gst-missing-plugins.c

This module must be a singleton, i.e. no instances are allowed. Thus, there is
no class.

Created on 25.04.2017

@author: Christian Stadelmann
"""

import logging

import gi

gi.require_version('GstPbutils', '1.0')
from gi.repository import GstPbutils

from xl import event
from xl.nls import gettext as _

LOGGER = logging.getLogger(__name__)

MISSING_PLUGIN_URL = "https://exaile.readthedocs.io/en/stable/user/faq.html"

# how to test:
# the helper binary is located at /usr/libexec/gstreamer/gst-install-plugins-helper


def handle_message(message, engine):
    """
    Handles `message` by checking whether it is a "missing plugin" message.
    If it is, takes all required steps to make sure that
        * playback is paused
        * the user is notified of the issue
        * the user gets a hint on which software to install

    @param message: a Gst.Message of type Gst.MessageType.Element
    @param engine: an instance of xl.player.gst.engine.ExaileGstEngine

    @return: True if the message was a "missing plugin" message and was
                being handled. This does not mean that the plugin installed
                successfully.
             False if the message should be handled by some other code
                because it is not related to a missing plugin.
    """
    if not GstPbutils.is_missing_plugin_message(message):
        return False

    __handle_plugin_missing_message(message, engine)
    return True


def __handle_plugin_missing_message(message, engine):

    desc = GstPbutils.missing_plugin_message_get_description(message)
    installer_details = GstPbutils.missing_plugin_message_get_installer_detail(message)
    LOGGER.warning("A plugin for %s is missing, stopping playback", desc)

    user_message = _(
        "A GStreamer 1.x plugin for %s is missing. "
        "Without this software installed, Exaile will not be able to play the current file. "
        "Please install the required software on your computer. See %s for details."
    ) % (desc, MISSING_PLUGIN_URL)
    # TODO make URL clickable by utilizing xlgui.widgets.dialogs.MessageBar

    engine.stop()
    __notify_user_on_error(user_message, engine)
    if GstPbutils.install_plugins_supported():
        if __run_installer_helper(installer_details):
            return
    LOGGER.warning("Installation of GStreamer plugins not supported on this platform.")


def __notify_user_on_error(message_text, engine):
    event.log_event('playback_error', engine.player, message_text)


def __run_installer_helper(installer_details):
    """

    @return True if the helper might have run. False if did not run for
                sure.
    """
    cntxt = __create_context()

    LOGGER.info("Prompting user to install missing codec(s): %s", installer_details)

    start_result = GstPbutils.install_plugins_async(
        [installer_details], cntxt, __installer_finished_callback
    )
    LOGGER.debug(
        "GstPbutils.install_plugins_async() return value: %s",
        GstPbutils.InstallPluginsReturn.get_name(start_result),
    )
    if start_result == GstPbutils.InstallPluginsReturn.INTERNAL_FAILURE:
        # should only happen when there is a bug in Exaile or its libs:
        LOGGER.error("Internal failure starting assisted GStreamer plugin installation")
        return False
    elif start_result == GstPbutils.InstallPluginsReturn.HELPER_MISSING:
        # we expect that to happen on some platforms
        LOGGER.warning("Helper missing for assisted installation of Gstreamer plugins")
        return False
    elif start_result == GstPbutils.InstallPluginsReturn.INSTALL_IN_PROGRESS:
        LOGGER.warning("Another assisted plugin installation is already in progress")
        return False
    elif start_result == GstPbutils.InstallPluginsReturn.STARTED_OK:
        LOGGER.info("Successfully started assisted GStreamer plugin installation")
        return True
    else:
        LOGGER.error(
            "Code should not be reached. "
            "Unexpected return value from install_plugins_async: %s",
            GstPbutils.InstallPluginsReturn.get_name(start_result),
        )
        return False


def __installer_finished_callback(result):
    # due to a bug in PackageKit, this function will be called immediately
    # after starting the helper: https://bugs.freedesktop.org/show_bug.cgi?id=100791
    LOGGER.debug(
        "GstPbutils.install_plugins_async() helper process exit code: %s",
        GstPbutils.InstallPluginsReturn.get_name(result),
    )

    if (
        result == GstPbutils.InstallPluginsReturn.SUCCESS
        or result == GstPbutils.InstallPluginsReturn.PARTIAL_SUCCESS
    ):
        # TODO notify user that installation of plugins was successful and ask
        # the user whether we may restart GStreamer engine to apply plugin updates,
        # because the user might have resumed playback in the meantime, and we do
        # not want to interrupt.
        #
        # engine.stop()
        # engine.destroy(permanent=False)
        # Gst.update_registry()
        # engine.initialize()
        pass
    elif result == GstPbutils.InstallPluginsReturn.NOT_FOUND:
        LOGGER.warning("GStreamer helper was unable to install missing plugin.")
        # we do not care about these, the user already got a notification how
        # to install plugins. There is nothing more we can do.
    elif (
        result == GstPbutils.InstallPluginsReturn.ERROR
        or result == GstPbutils.InstallPluginsReturn.CRASHED
        or result == GstPbutils.InstallPluginsReturn.INVALID
        or result == GstPbutils.InstallPluginsReturn.INTERNAL_FAILURE
    ):
        LOGGER.error(
            "GStreamer plugin helper failed with %s",
            GstPbutils.InstallPluginsReturn.get_name(result),
        )
    elif result == GstPbutils.InstallPluginsReturn.USER_ABORT:
        LOGGER.info("User aborted the GStreamer plugin installation.")
        # the user decided not to install any software, which might have been on purpose,
        # so we do not want to ask again immediately.
    else:
        LOGGER.error(
            "Code should not be reached. "
            "Unexpected return value from install_plugins_async callback: %s",
            GstPbutils.InstallPluginsReturn.get_name(result),
        )


def __create_context():
    LOGGER.info("Initializing connector for GstPbutils...")
    cntxt = GstPbutils.InstallPluginsContext()
    cntxt.set_confirm_search(True)

    # See https://standards.freedesktop.org/desktop-entry-spec/latest/ape.html
    cntxt.set_desktop_id("exaile.desktop")
    # TODO
    # cntxt.set_startup_notification_id()
    # cntxt.set_xid()
    return cntxt
