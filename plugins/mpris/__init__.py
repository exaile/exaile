__all__ = ["exaile_mpris"]

import exaile_mpris
import logging

LOG = logging.getLogger("exaile.plugins.mpris")

_MPRIS = None

def enable(exaile):
    LOG.debug("Enabling MPRIS")
    if _MPRIS is None:
        global _MPRIS
        _MPRIS = exaile_mpris.ExaileMpris(exaile)
    _MPRIS.exaile = exaile
    _MPRIS.acquire()

def disable(exaile):
    LOG.debug("Disabling MPRIS")
    _MPRIS.release()
