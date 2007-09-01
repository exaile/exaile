#!/usr/bin/env python
# -*- coding: utf-8 -*-

import dbus, gobject, gtk, os
import xl.plugins as plugins


# Plugin description
PLUGIN_NAME        = 'IM Status'
PLUGIN_ICON        = None
PLUGIN_ENABLED     = False
PLUGIN_AUTHORS     = ['Ingelrest François <Athropos@gmail.com>']
PLUGIN_VERSION     = '0.12'
PLUGIN_DESCRIPTION = r"""Sets the online status of your instant messenger client according to the music you are listening to.\n\nSupported IM clients are:\n * Gaim (>= 2.0 beta6)\n * Gajim\n * Gossip\n * Pidgin"""

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
mHandlers           = plugins.SignalContainer()  # Handlers used by this plugin
mIMClients          = []                         # Active IM clients
mNowPlaying         = ''                         # The currently used status message
mCurrentTrack       = None                       # The track currently being played
mSupportedIMClients = []                         # Supported IM clients: this list is populated later in the code

##############################################################################

class Pidgin :

    def __init__(self, dbusInterface) :
        """
            Constructor
        """
        self.dbusInterface = dbusInterface

    def listAccounts(self) :
        """
            Purple merges all accounts, so we return a default one
            Each account is associated with:
                * A boolean -> True if the status of this account was changed on the previous track change
        """
        return {'GenericAccount' : False}

    def setAccountStatusMsg(self, account, msg) :
        """
            Change the status message of the given account
            Why is it so complex with Purple??
            Return true if the message is successfully updated
        """
        try :
            current    = self.dbusInterface.PurpleSavedstatusGetCurrent()
            statusType = self.dbusInterface.PurpleSavedstatusGetType(current)
            statusId   = self.dbusInterface.PurplePrimitiveGetIdFromType(statusType)
            if statusId in ['available'] :
                saved = self.dbusInterface.PurpleSavedstatusNew('', statusType)
                self.dbusInterface.PurpleSavedstatusSetMessage(saved, msg)
                self.dbusInterface.PurpleSavedstatusActivate(saved)
                return True
        except :
            pass

        return False

##############################################################################

class Gaim :

    def __init__(self, dbusInterface) :
        """
            Constructor
        """
        self.dbusInterface = dbusInterface

    def listAccounts(self) :
        """
            Gaim merges all accounts, so we return a default one
            Each account is associated with:
                * A boolean -> True if the status of this account was changed on the previous track change
        """
        return {'GenericAccount' : False}

    def setAccountStatusMsg(self, account, msg) :
        """
            Change the status message of the given account
            Why is it so complex with Gaim??
            Return true if the message is successfully updated
        """
        try :
            current    = self.dbusInterface.GaimSavedstatusGetCurrent()
            statusType = self.dbusInterface.GaimSavedstatusGetType(current)
            statusId   = self.dbusInterface.GaimPrimitiveGetIdFromType(statusType)
            if statusId in ['available'] :
                saved = self.dbusInterface.GaimSavedstatusNew('', statusType)
                self.dbusInterface.GaimSavedstatusSetMessage(saved, msg)
                self.dbusInterface.GaimSavedstatusActivate(saved)
                return True
        except :
            pass

        return False

##############################################################################

class Gajim :

    def __init__(self, dbusInterface) :
        """
            Constructor
        """
        self.dbusInterface = dbusInterface

    def listAccounts(self) :
        """
            Return a list of existing accounts
            Each account is associated with:
                * A boolean -> True if the status of this account was changed on the previous track change
        """
        try :
            return dict([(account, False) for account in self.dbusInterface.list_accounts()])
        except :
            return {}

    def setAccountStatusMsg(self, account, msg) :
        """
            Change the status message of the given account
            Return true if the message is successfully updated
        """
        try :
            currentStatus = self.dbusInterface.get_status(account)
            if currentStatus in ['online', 'chat'] :
                self.dbusInterface.change_status(currentStatus, msg, account)
                return True
        except :
            pass

        return False

##############################################################################

class Gossip :

    def __init__(self, dbusInterface) :
        """
            Constructor
        """
        self.dbusInterface = dbusInterface

    def listAccounts(self) :
        """
            Gossip merges all accounts, so we return a default one
            Each account is associated with:
                * A boolean -> True if the status of this account was changed on the previous track change
        """
        return {'GenericAccount' : False}

    def setAccountStatusMsg(self, account, msg) :
        """
            Change the status message of the given account
            Return true if the message is successfully updated
        """
        try :
            currentStatus, currentMsg = self.dbusInterface.GetPresence('')
            if currentStatus in ['available'] :
                self.dbusInterface.SetPresence(currentStatus, msg)
                return True
        except :
            pass

        return False

##############################################################################

# Elements associated with each supported IM clients
(
    IM_DBUS_SERVICE_NAME,
    IM_DBUS_OBJECT_NAME,
    IM_DBUS_INTERFACE_NAME,
    IM_CLASS,
    IM_INSTANCE,
    IM_ACCOUNTS
) = range(6)


# All specific classes have been defined, so we can now populate the list of supported IM clients
mSupportedIMClients = [
    ['im.pidgin.purple.PurpleService', '/im/pidgin/purple/PurpleObject',      'im.pidgin.purple.PurpleInterface',      Pidgin,   None, {}],  # Pidgin
    ['net.sf.gaim.GaimService',        '/net/sf/gaim/GaimObject',             'net.sf.gaim.GaimInterface',             Gaim,   None, {}],  # Gaim
    ['org.gajim.dbus',                 '/org/gajim/dbus/RemoteObject',        'org.gajim.dbus.RemoteInterface',        Gajim,  None, {}],  # Gajim
    ['org.gnome.Gossip',               '/org/gnome/Gossip',                   'org.gnome.Gossip',                      Gossip, None, {}]   # Gossip
]


def setStatusMsg(nowPlaying) :
    """
        Try to update the status of all accounts of all detected IM clients
    """
    global mNowPlaying

    for client in mIMClients :
        for account,wasUpdated in client[IM_ACCOUNTS].iteritems() :
            if nowPlaying != mNowPlaying or not wasUpdated :
                client[IM_ACCOUNTS][account] = client[IM_INSTANCE].setAccountStatusMsg(account, nowPlaying)
    mNowPlaying = nowPlaying


def updateStatus() :
    """
        Information about the current track has changed
    """
    global mCurrentTrack

    mCurrentTrack = APP.player.current

    # Construct the new status message
    nowPlaying = APP.settings.get_str('format', DEFAULT_STATUS_FORMAT, PID)
    for field in TRACK_FIELDS :
        nowPlaying = nowPlaying.replace('{%s}' % field, unicode(getattr(mCurrentTrack, field)))

    if APP.player.is_paused() and APP.settings.get_boolean('updateOnPause', DEFAULT_UPDATE_ON_PAUSE, PID) :
        nowPlaying = nowPlaying + ' [paused]'

    # And try to update the status of all IM clients
    setStatusMsg(nowPlaying)


def stop_track(exaile, track) :
    """
        Called when Exaile quits or when playback stops
    """
    global mCurrentTrack

    mCurrentTrack = None

    # Stop event is sent also when a track is finished, even if Exaile is going to play the next one
    # Since we don't want to change the status between each track, we add a delay of 1 sec. before doing anything
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
            setStatusMsg(APP.settings.get_str('stopStatus', DEFAULT_STOP_STATUS, PID))
    return False


def initialize(self = None):
    """
        Called when the plugin is enabled
    """
    global mIMClients
    oldNumber      = len(mIMClients) 
    mIMClients     = []
    activeServices = dbus.SessionBus().get_object('org.freedesktop.DBus', '/org/freedesktop/DBus').ListNames()

    for client in mSupportedIMClients :
        if client[IM_DBUS_SERVICE_NAME] in activeServices :
            obj       = dbus.SessionBus().get_object(client[IM_DBUS_SERVICE_NAME], client[IM_DBUS_OBJECT_NAME])
            interface = dbus.Interface(obj, client[IM_DBUS_INTERFACE_NAME])

            client[IM_INSTANCE] = client[IM_CLASS](interface)
            client[IM_ACCOUNTS] = client[IM_INSTANCE].listAccounts()

            mIMClients.append(client)
            
            
    # If there is at least one active IM client, we can connect our handlers
    if oldNumber == 0 :
        if len(mIMClients) != 0 :
            mHandlers.connect(APP.player, 'stop-track',                 stop_track)
            mHandlers.connect(APP.player, 'pause-toggled',              lambda exaile, track : updateStatus())
            mHandlers.connect(APP,        'track-information-updated',  lambda arg : updateStatus())
    else :
        if len(mIMClients) == 0 :
            mHandlers.disconnect(APP.player, 'stop-track',                 stop_track)
            mHandlers.disconnect(APP.player, 'pause-toggled',              lambda exaile, track : updateStatus())
            mHandlers.disconnect(APP,        'track-information-updated',  lambda arg : updateStatus())
    
    #print "Working clients: ", mIMClients

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
    resetButton = gtk.Button('Reset')
    tmpBox.pack_start(resetButton, False, False, 0)
    resetButton.connect('clicked', initialize)

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
