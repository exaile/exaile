import copy
from gettext import gettext as _
import gtk

import xlmisc, media, library, common

TAG_NO_ERROR, TAG_MISSING, TAG_DIFFERENT, TAG_UNSUPPORTED, TAG_MULTI = range(0, 5)

class TrackGroup(object):
    """
        Workhorse class for the tag editor... all operations are done
        to a group of tracks.

        When using this class, remember that everything is returned as
        a list, even if its length is only 1.
    """
    def __init__(self, tracks=None):
        """
            Classify the different properties of the group
        """
        self.tracks = []
        self.is_file = True # if all tracks are files
        self.multi = True   # if every track supports multiple tag values
        
        if not tracks: 
            return 

        for song in tracks:
            self.is_file &= song.is_file()
            self.multi &= song.is_multi()
        
        if not self.is_file:
            raise IsFileException('>0 tracks in the group are not files.')
            return

        self.tracks = tracks

    def __len__(self):
        return len(self.tracks)

    def __iter__(self):
        return iter(self.tracks)

    def pop(self, i):
        self.tracks.pop(i)

    def get_tag_status(self, tag):
        """
            Returns the status of a tag in this group. Values are either
            one of the errors listed above (TAG_MISSING etc) or a string
            if the tag is the same for all tracks
        """
        values = []
        change = True
        for song in self.tracks:
            change &= song.can_change(tag)
            v = song.tags[tag]
            if v: values.append(v)

        if not values: 
            return None

        if not change:
            # at least one track doesn't support this tag
            return TAG_UNSUPPORTED

        if len(values) < len(self.tracks):
            # some tracks are missing this tag
            return TAG_MISSING
        
        if not self.multi:
            # flag an error if we find multiple tag values without all tracks
            # supporting it
            if True in [len(v) > i for v in values]:
                return TAG_MULTI
            
        cmp = sorted(values[0])
        if False in [cmp == sorted(x) for x in values]:
            return TAG_DIFFERENT

        # if our poor tag has survived, it's the same for all tracks
        return values[0]

    def make_model(self):
        """
            Scan the tags from the files and construct a ListStore of them
        """
        TAGNAME, VALUE, OLDVALUE, ERROR, ADDED, REMOVED, EDITED = range(0, 7)
        model = gtk.ListStore(str, str, str, int, bool, bool, bool)

        for tag in xlmisc.VALID_TAGS:
            row = [tag, None, None, TAG_NO_ERROR, False, False, False]
            status = self.get_tag_status(tag)
            if status is None: 
                continue
            elif type(status) is int: 
                row[ERROR] = status
                model.append(row)
            elif type(status) is list:
                for v in status:
                    row[VALUE] = row[OLDVALUE] = v
                    model.append(row)

        return model
                
    def write_tags(self, exaile, model):
        """
            Write the changes to disk. Returns a list of strings (errors)
        """
        TAGNAME, VALUE, OLDVALUE, ERROR, ADDED, REMOVED, EDITED = range(0, 7)
        errors = []
        to_add = common.ldict()
        for track in self.tracks:
            for row in model:
                tag = row[TAGNAME]
                if row[ERROR]:
                    if row[REMOVED]:
                        track.tags[tag] = []
                        continue
                else:
                    if row[REMOVED]:
                        if row[ADDED]: continue # add + remove = nothing
                        for i, v in enumerate(track.tags[tag]):
                            if v == row[VALUE]:
                                del(track.tags[tag][i])
                                break
                    elif row[ADDED]:
                        if to_add.has_key(tag):
                            to_add[tag].append(row[VALUE])
                        else:
                            to_add[tag] = row[VALUE]
                    elif row[EDITED]:
                        for i, v in enumerate(track.tags[tag]):
                            if v == row[OLDVALUE]:
                                track.tags[tag][i] = row[VALUE]

            for tag, val in to_add.iteritems():
                if track.tags.has_key(tag):
                    track.tags[tag].extend(val)
                else:
                    track.tags[tag] = val

            try:
                media.write_tag(track)
                library.save_track_to_db(exaile.db, track)
                exaile.tracks.refresh_row(track)
            except:
                errors.append(_("Unknown error writing tag for %s") % track.loc)
                xlmisc.log_exception()

        exaile.tracks.queue_draw()
        exaile.db.db.commit()

        return errors
