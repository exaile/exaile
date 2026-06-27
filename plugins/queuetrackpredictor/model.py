# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

from collections import Counter, defaultdict
from datetime import datetime, timezone

MODEL_VERSION = 1
DEFAULT_BPM_BAND_SIZE = 5
MAX_CONTEXT_LENGTH = 3
DEFAULT_MAX_SUGGESTIONS = 10


def _get_track_location(track):
    try:
        return track.get_loc_for_io()
    except Exception:
        return None


def _get_track_bpm(track):
    try:
        bpm = track.get_tag_raw('bpm', True)
    except Exception:
        return None

    if bpm in (None, ''):
        return None

    try:
        return int(round(float(bpm)))
    except (TypeError, ValueError):
        return None


def bucket_bpm(bpm, band_size=DEFAULT_BPM_BAND_SIZE):
    if bpm is None:
        return None
    if band_size <= 0:
        return bpm
    return bpm - (bpm % band_size)


def track_features(track, get_track_groups, bpm_band_size=DEFAULT_BPM_BAND_SIZE):
    groups = get_track_groups(track) or []
    return (
        tuple(sorted(groups)),
        bucket_bpm(_get_track_bpm(track), bpm_band_size),
    )


def make_track_summary(track, get_track_groups, bpm_band_size=DEFAULT_BPM_BAND_SIZE):
    return {
        'groups': track_features(track, get_track_groups, bpm_band_size)[0],
        'bpm_band': track_features(track, get_track_groups, bpm_band_size)[1],
        'title': _get_track_display(track, 'title'),
        'artist': _get_track_display(track, 'artist'),
    }


def _get_track_display(track, tag):
    try:
        return track.get_tag_display(tag)
    except Exception:
        return ''


def build_model(playlists, get_track_groups, bpm_band_size=DEFAULT_BPM_BAND_SIZE):
    transition_counts = defaultdict(Counter)
    candidate_features = {}
    playlist_count = 0
    track_count = 0

    for playlist in playlists:
        tracks = list(playlist)
        playlist_count += 1
        track_count += len(tracks)

        feature_cache = [
            track_features(track, get_track_groups, bpm_band_size) for track in tracks
        ]

        for track in tracks:
            loc = _get_track_location(track)
            if loc is not None and loc not in candidate_features:
                candidate_features[loc] = make_track_summary(
                    track, get_track_groups, bpm_band_size
                )

        for idx in range(1, len(tracks)):
            next_loc = _get_track_location(tracks[idx])
            if next_loc is None:
                continue
            for context_length in range(1, min(MAX_CONTEXT_LENGTH, idx) + 1):
                context = tuple(feature_cache[idx - context_length : idx])
                transition_counts[context][next_loc] += 1

    return {
        'version': MODEL_VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'bpm_band_size': bpm_band_size,
        'playlist_count': playlist_count,
        'track_count': track_count,
        'transition_counts': {
            context: dict(counts) for context, counts in transition_counts.items()
        },
        'candidate_features': candidate_features,
    }


def get_suggestion_locations(
    model,
    previous_tracks,
    get_track_groups,
    max_suggestions=DEFAULT_MAX_SUGGESTIONS,
    excluded_locations=None,
):
    if model.get('version') != MODEL_VERSION:
        raise ValueError("Unsupported queue predictor model version")

    if len(previous_tracks) < 1:
        return []

    bpm_band_size = model.get('bpm_band_size', DEFAULT_BPM_BAND_SIZE)
    context = tuple(
        track_features(track, get_track_groups, bpm_band_size)
        for track in previous_tracks[-MAX_CONTEXT_LENGTH:]
    )

    transition_counts = model.get('transition_counts', {})
    counts = Counter()
    for suffix_length in range(len(context) - 1, 0, -1):
        suffix = context[-suffix_length:]
        weight = suffix_length + 1
        counts.update(
            {
                loc: count * weight
                for loc, count in transition_counts.get(suffix, {}).items()
            }
        )
    counts.update(_get_similar_candidate_counts(model, context[-1]))

    seen = set()
    previous_locations = {_get_track_location(track) for track in previous_tracks}
    previous_locations.discard(None)
    excluded_locations = set(excluded_locations or [])
    if len(context) > 1:
        excluded_locations.update(transition_counts.get(context, {}).keys())
    suggestions = []

    for loc, _count in _rank_counts(counts):
        if loc in excluded_locations:
            continue
        if loc in previous_locations:
            continue
        if loc in seen:
            continue
        seen.add(loc)
        suggestions.append(loc)
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


def _get_similar_candidate_counts(model, last_feature):
    candidate_features = model.get('candidate_features', {})
    global_counts = Counter()
    for candidates in model.get('transition_counts', {}).values():
        global_counts.update(candidates)

    counts = Counter()
    for loc, count in global_counts.items():
        features = candidate_features.get(loc)
        if features is None:
            continue
        score = _candidate_similarity_score(last_feature, features)
        if score > 0:
            counts[loc] = (score * 1000) + count
    return counts


def _candidate_similarity_score(last_feature, candidate_features):
    last_groups, last_bpm_band = last_feature
    candidate_groups = set(candidate_features.get('groups') or ())
    candidate_bpm_band = candidate_features.get('bpm_band')

    score = len(set(last_groups) & candidate_groups) * 4
    if (
        last_bpm_band is not None
        and candidate_bpm_band is not None
        and abs(last_bpm_band - candidate_bpm_band) <= 10
    ):
        score += 1
    return score


def _rank_counts(counts):
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def resolve_suggestion_tracks(
    collection, locations, max_suggestions=DEFAULT_MAX_SUGGESTIONS
):
    tracks = []
    for loc in locations:
        track = collection.get_track_by_loc(loc)
        if track is not None:
            tracks.append(track)
        if len(tracks) >= max_suggestions:
            break
    return tracks
