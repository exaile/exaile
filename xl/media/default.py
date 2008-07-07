from xl import common

def fill_tag_from_path(tr):
    tr['title'] = tr.get_loc()

def can_change(tag):
    return False

def is_multi():
    return False

# vim: et sts=4 sw=4

