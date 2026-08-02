import importlib.util
import os


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    '..',
    'plugins',
    'queuetrackpredictor',
    'model.py',
)
SPEC = importlib.util.spec_from_file_location('queuetrackpredictor_model', MODEL_PATH)
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


class FakeTrack:
    def __init__(self, loc, groups=None, bpm=None, title=None, artist=None):
        self.loc = loc
        self.groups = set(groups or [])
        self.bpm = bpm
        self.title = title or loc
        self.artist = artist or ''

    def get_loc_for_io(self):
        return self.loc

    def get_tag_raw(self, tag, join=False):
        if tag == 'bpm':
            return self.bpm
        return None

    def get_tag_display(self, tag):
        if tag == 'title':
            return self.title
        if tag == 'artist':
            return self.artist
        return ''


def get_groups(track):
    return track.groups


def test_track_features_sort_groups_and_bucket_bpm():
    track = FakeTrack('a', groups={'swing', 'blues'}, bpm='123')

    assert model.track_features(track, get_groups) == (('blues', 'swing'), 120)


def test_build_model_counts_feature_transitions():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    d = FakeTrack('d', groups={'hot'}, bpm=131)
    e = FakeTrack('e', groups={'blue'}, bpm=100)

    trained = model.build_model([[a, b, c, e], [a, b, c, e], [a, b, d]], get_groups)
    one_track_context = (model.track_features(b, get_groups),)
    two_track_context = (
        model.track_features(a, get_groups),
        model.track_features(b, get_groups),
    )
    three_track_context = (
        model.track_features(a, get_groups),
        model.track_features(b, get_groups),
        model.track_features(c, get_groups),
    )

    assert trained['transition_counts'][one_track_context] == {'c': 2, 'd': 1}
    assert trained['transition_counts'][two_track_context] == {'c': 2, 'd': 1}
    assert trained['transition_counts'][three_track_context] == {'e': 2}
    assert trained['playlist_count'] == 3
    assert trained['track_count'] == 11


def test_get_suggestion_locations_uses_broad_feature_matches_and_limits():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    d = FakeTrack('d', groups={'hot'}, bpm=131)
    e = FakeTrack('e', groups={'hot'}, bpm=132)
    x = FakeTrack('x', groups={'other'}, bpm=90)
    y = FakeTrack('y', groups={'hot'}, bpm=135)

    trained = model.build_model(
        [[a, b, d], [a, b, c], [a, b, c], [a, b, e]], get_groups
    )

    assert model.get_suggestion_locations(
        trained, [x, y], get_groups, max_suggestions=2
    ) == ['c', 'd']

    assert model.get_scored_suggestion_locations(
        trained, [x, y], get_groups, max_suggestions=2
    ) == [('c', 5004), ('d', 5002)]


def test_get_suggestion_locations_returns_empty_without_context_match():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    x = FakeTrack('x', groups={'other'}, bpm=90)
    y = FakeTrack('y', groups={'other'}, bpm=95)

    trained = model.build_model([[a, b, c]], get_groups)

    assert model.get_suggestion_locations(trained, [x, y], get_groups) == []


def test_get_suggestion_locations_uses_one_track_context_at_playlist_start():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    d = FakeTrack('d', groups={'cool'}, bpm=124)
    e = FakeTrack('e', groups={'blue'}, bpm=100)

    trained = model.build_model([[a, b, c], [d, e, c]], get_groups)

    assert model.get_suggestion_locations(trained, [b], get_groups) == ['c']


def test_get_suggestion_locations_falls_back_to_similar_candidates():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    x = FakeTrack('x', groups={'other'}, bpm=90)
    y = FakeTrack('y', groups={'hot'}, bpm=136)

    trained = model.build_model([[a, b, c]], get_groups)

    assert model.get_suggestion_locations(trained, [x, y], get_groups) == ['c']


def test_get_suggestion_locations_does_not_use_exact_pair_match():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    d = FakeTrack('d', groups={'warm'}, bpm=118)
    e = FakeTrack('e', groups={'other'}, bpm=90)
    f = FakeTrack('f', groups={'cool'}, bpm=126)

    trained = model.build_model([[a, b, c], [d, e, f]], get_groups)

    assert model.get_suggestion_locations(trained, [a, b], get_groups) == ['f']


def test_get_suggestion_locations_does_not_use_exact_three_track_match():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'blue'}, bpm=100)
    d = FakeTrack('d', groups={'hot'}, bpm=130)
    e = FakeTrack('e', groups={'other'}, bpm=90)
    f = FakeTrack('f', groups={'cool'}, bpm=126)

    trained = model.build_model([[a, b, c, d], [e, b, c, f]], get_groups)

    assert model.get_suggestion_locations(trained, [a, b, c], get_groups) == ['f']


def test_get_suggestion_locations_can_exclude_known_next_track():
    a = FakeTrack('a', groups={'warm'}, bpm=120)
    b = FakeTrack('b', groups={'cool'}, bpm=122)
    c = FakeTrack('c', groups={'hot'}, bpm=130)
    d = FakeTrack('d', groups={'cool'}, bpm=124)
    e = FakeTrack('e', groups={'warm'}, bpm=118)
    f = FakeTrack('f', groups={'cool'}, bpm=126)

    trained = model.build_model([[a, b, c], [d, e, f]], get_groups)

    assert model.get_suggestion_locations(
        trained, [a, b], get_groups, max_suggestions=1, excluded_locations={'c'}
    ) == ['f']


def test_diversity_reranking_can_promote_novel_candidates():
    recent = FakeTrack('recent', groups={'house'}, bpm=125, artist='Repeated')
    trained = {
        'bpm_band_size': 5,
        'candidate_features': {
            'same': {
                'groups': ('house',),
                'bpm_band': 125,
                'artist': 'Repeated',
            },
            'similar': {
                'groups': ('house',),
                'bpm_band': 125,
                'artist': 'Other',
            },
            'novel': {
                'groups': ('disco',),
                'bpm_band': 115,
                'artist': 'New',
            },
        },
    }
    candidates = [('same', 100), ('similar', 95), ('novel', 80)]

    assert model.rerank_suggestions_for_diversity(
        trained, candidates, [recent], get_groups, max_suggestions=3, diversity=0
    ) == candidates
    assert model.rerank_suggestions_for_diversity(
        trained, candidates, [recent], get_groups, max_suggestions=3, diversity=100
    )[0][0] == 'novel'


def test_diversity_reranking_varies_the_result_list():
    trained = {
        'candidate_features': {
            'house-1': {'groups': ('house',), 'bpm_band': 125, 'artist': 'One'},
            'house-2': {'groups': ('house',), 'bpm_band': 125, 'artist': 'Two'},
            'disco': {'groups': ('disco',), 'bpm_band': 115, 'artist': 'Three'},
        }
    }
    candidates = [('house-1', 100), ('house-2', 99), ('disco', 90)]

    reranked = model.rerank_suggestions_for_diversity(
        trained, candidates, [], get_groups, max_suggestions=2, diversity=60
    )

    assert [location for location, score in reranked] == ['house-1', 'disco']


def test_invalid_bpm_is_bucketed_as_none():
    track = FakeTrack('a', groups={'warm'}, bpm='not-a-number')

    assert model.track_features(track, get_groups) == (('warm',), None)


def test_resolve_suggestion_tracks_skips_missing_locations():
    a = FakeTrack('a')
    c = FakeTrack('c')

    class Collection:
        def get_track_by_loc(self, loc):
            return {'a': a, 'c': c}.get(loc)

    assert model.resolve_suggestion_tracks(Collection(), ['a', 'b', 'c']) == [a, c]
    assert model.resolve_scored_suggestion_tracks(
        Collection(), [('a', 10), ('b', 9), ('c', 8)]
    ) == [(a, 10), (c, 8)]
