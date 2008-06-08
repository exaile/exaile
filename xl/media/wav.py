from xl import common

TYPE = 'wav'

def fill_tag_from_path(tr):
    tr['title'] = tr.get_loc().encode(common.get_default_encoding())

def can_change(tag):
    return False

def is_multi():
    return False

# vim: et sts=4 sw=4

