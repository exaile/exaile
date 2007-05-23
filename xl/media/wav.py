import xl.xlmisc

TYPE = 'wav'

def fill_tag_from_path(tr):
    tr.title = tr.loc.encode(xl.xlmisc.get_default_encoding())
