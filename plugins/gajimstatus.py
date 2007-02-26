#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    This plugin sets online status of Gajim with currently playing track.
"""

import gtk, gobject, os, plugins

# Plugin description
PLUGIN_NAME        = 'Gajim Status'
PLUGIN_ICON        = None
PLUGIN_ENABLED     = False
PLUGIN_AUTHORS     = ['Ingelrest François <Athropos@gmail.com>']
PLUGIN_VERSION     = '0.06'
PLUGIN_DESCRIPTION = 'Sets online status of Gajim with currently playing track'

# Possible actions when Exaile quits or stops playing
(
    DO_NOTHING,
    CHANGE_STATUS
) = range(2)

# Constants
PID                     = plugins.name(__file__)
TRACK_FIELDS            = ('album', 'artist', 'bitrate', 'genre', 'length', 'rating', 'title', 'track', 'year')
DEFAULT_STOP_ACTION     = CHANGE_STATUS
DEFAULT_STOP_STATUS     = 'Exaile is stopped'
DEFAULT_STATUS_FORMAT   = '♫ {artist} - {album} ♫'
DEFAULT_UPDATE_ON_PAUSE = False

# Global variables
mAccounts     = {}                         # All Gajim accounts
mHandlers     = plugins.SignalContainer()  # Handlers used by this plugin
mNowPlaying   = ''                         # The currently used status message
mCurrentTrack = None                       # The track currently being played


def getAccountStatus(account):
    """
        Return the status of the given account
        If it doesn't exist, return 'offline'
    """
    status = os.popen('gajim-remote get_status "%s"' % (account)).readlines()
    if len(status) == 0:
        return 'offline'
    return status[0].strip()


def setAccountStatusMsg(account, msg):
    """
        Change the status message of the given account
        The message will be changed only if the current status of the account is either 'online' or 'chat'
    """
    currentStatus = getAccountStatus(account)
    if currentStatus in ['online', 'chat']:
        os.system('gajim-remote change_status "%s" "%s" "%s"' % (currentStatus, msg, account))
        return True
    return False


def updateStatus() :
    """
        Try to update the status of all accounts
    """
    global mNowPlaying, mCurrentTrack

    mCurrentTrack = APP.player.current

    # Construct the new status message
    nowPlaying = APP.settings.get_str('format', DEFAULT_STATUS_FORMAT, PID)
    for field in TRACK_FIELDS :
        nowPlaying = nowPlaying.replace('{%s}' % field, unicode(getattr(mCurrentTrack, field)))

    if APP.player.is_paused() and APP.settings.get_boolean('updateOnPause', DEFAULT_UPDATE_ON_PAUSE, PID) :
        nowPlaying = nowPlaying + ' [paused]'

    # Try to update the status of each account
    for account,wasUpdated in mAccounts.iteritems() :
        if nowPlaying != mNowPlaying or not wasUpdated :
            mAccounts[account] = setAccountStatusMsg(account, nowPlaying)
    mNowPlaying = nowPlaying


def stop_track(exaile, track) :
    """
        Called when Exaile quits or when playback stops
    """
    global mCurrentTrack

    mCurrentTrack = None

    # Stop event is sent also when a track is finished, even if Exaile is going to play the next one
    # Since we don't want to change the status of Gajim between each track, we add a delay of 1 sec. before doing anything
    gobject.timeout_add(1000, onStopTimer)


def onStopTimer() :
    """
        Called 1 sec. after the reception of a stop event
    """
    global mNowPlaying

    # If mCurrentTrack is still None, it means that Exaile has not started to play another track
    # In this case, we may assume that it is really stopped
    if mCurrentTrack is None :
        mNowPlaying = ''
        if APP.settings.get_int('stopAction', DEFAULT_STOP_ACTION, PID) == CHANGE_STATUS :
            status = APP.settings.get_str('stopStatus', DEFAULT_STOP_STATUS, PID)
            for account in mAccounts.keys() :
                setAccountStatusMsg(account, status)
    return False


def initialize():
    """
        Called when the plugin is enabled
    """
    global mAccounts

    # Retrieve Gajim accounts: the dictionary will be empty if Gajim is not running
    # Each account is associated with:
    #  * A boolean -> True if the status of this account was changed on the previous track change
    mAccounts = dict([(str.strip(), False) for str in os.popen('gajim-remote list_accounts').readlines()])
    if len(mAccounts) != 0 :
        mHandlers.connect(APP, 'stop-track',                stop_track)
        mHandlers.connect(APP, 'pause-toggled',             lambda exaile, track : updateStatus())
        mHandlers.connect(APP, 'track-information-updated', lambda arg : updateStatus())
    return True


def destroy() :
    """
        Called when the plugin is disabled
    """
    mHandlers.disconnect_all()


def showHelp(widget, data=None) :
    """
        Display a dialog box with some help about status format
    """
    msg = 'Any field of the form <b>{field}</b> will be replaced by the corresponding value.\n\nAvailable fields are '
    for field in TRACK_FIELDS :
        msg = msg + '<i>' + field + '</i>, '
    dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK)
    dlg.set_markup(msg[:-2])
    dlg.run()
    dlg.destroy()


def configure() :
    """
        Called when the user wants to configure the plugin
    """
    dlg = plugins.PluginConfigDialog(APP.window, PLUGIN_NAME)

    align = gtk.Alignment()
    align.set_padding(5, 5, 5, 5)
    dlg.get_child().add(align)
    mainBox = gtk.VBox()
    mainBox.set_spacing(5)
    align.add(mainBox)

    # Upper part: status format
    frame = gtk.Frame('')
    frame.get_label_widget().set_markup('<b> Status message: </b>')
    mainBox.pack_start(frame, True, True, 0)
    align = gtk.Alignment(0, 0, 1, 1)
    align.set_padding(5, 5, 5, 5)
    frame.add(align)
    tmpBox = gtk.HBox()
    tmpBox.set_spacing(5)
    entryFormat = gtk.Entry()
    entryFormat.set_text(APP.settings.get_str('format', DEFAULT_STATUS_FORMAT, PID))
    button = gtk.Button('Help', gtk.STOCK_HELP)
    tmpBox.pack_start(entryFormat, True, True)
    tmpBox.pack_start(button)
    button.connect('clicked', showHelp)
    align.add(tmpBox)

    # Middle part: what should be done when Exaile quits of stops playing
    frame = gtk.Frame('')
    frame.get_label_widget().set_markup('<b> When Exaile stops playing or quits: </b>')
    mainBox.pack_start(frame, False, False, 0)
    tmpBox = gtk.VBox()
    tmpBox.set_spacing(5)
    align = gtk.Alignment()
    align.set_padding(5, 5, 5, 5)
    frame.add(align)
    align.add(tmpBox)
    radioDoNothing = gtk.RadioButton(None, 'Do nothing')
    radioSetStatus = gtk.RadioButton(radioDoNothing, 'Set status to:')
    if APP.settings.get_int('stopAction', DEFAULT_STOP_ACTION, PID) == DO_NOTHING :
        radioDoNothing.set_active(True)
    else :
        radioSetStatus.set_active(True)
    tmpBox.pack_start(radioDoNothing, False, False, 0)
    box2 = gtk.HBox()
    entryStopStatus = gtk.Entry()
    entryStopStatus.set_text(APP.settings.get_str('stopStatus', DEFAULT_STOP_STATUS, PID))
    box2.pack_start(radioSetStatus, False, False, 0)
    box2.pack_start(entryStopStatus, False, False, 0)
    tmpBox.pack_start(box2, False, False, 0)

    # Lower part: miscellaneous
    frame = gtk.Frame('')
    frame.get_label_widget().set_markup('<b> Miscellaneous: </b>')
    mainBox.pack_start(frame, False, False, 0)
    tmpBox = gtk.VBox()
    tmpBox.set_spacing(5)
    align = gtk.Alignment()
    align.set_padding(5, 5, 5, 5)
    frame.add(align)
    align.add(tmpBox)
    checkUpdateOnPause = gtk.CheckButton('Update status when track is paused')
    tmpBox.pack_start(checkUpdateOnPause, False, False, 0)
    checkUpdateOnPause.set_active(APP.settings.get_boolean('updateOnPause', DEFAULT_UPDATE_ON_PAUSE, PID))

    dlg.show_all()
    result = dlg.run()
    dlg.hide()

    if result == gtk.RESPONSE_OK :
        if radioDoNothing.get_active() :
            APP.settings.set_int('stopAction', DO_NOTHING, PID)
        else :
            APP.settings.set_int('stopAction', CHANGE_STATUS, PID)
        APP.settings.set_str('stopStatus',        entryStopStatus.get_text(),      PID)
        APP.settings.set_str('format',            entryFormat.get_text(),          PID)
        APP.settings.set_boolean('updateOnPause', checkUpdateOnPause.get_active(), PID)
        if mCurrentTrack is not None :
            updateStatus()
