# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

MODEL_VERSION = 1
DEFAULT_BPM_BAND_SIZE = 5
MAX_CONTEXT_LENGTH = 3
DEFAULT_MAX_SUGGESTIONS = 10
DEFAULT_DIVERSITY = 50
DEFAULT_BPM_BIAS = 0
BPM_BIAS_FULL_EFFECT_DELTA = 30
TAG_BIAS_FACTORS = {
    -2: 0.5,
    -1: 0.75,
    0: 1.0,
    1: 4.0 / 3.0,
    2: 2.0,
}


def normalize_model_tuning(model, tuning):
    """Validate runtime tuning stored separately from a trained model."""
    if not isinstance(tuning, dict):
        tuning = {}
    raw_tag_biases = tuning.get('tag_biases', {})
    if not isinstance(raw_tag_biases, dict):
        raw_tag_biases = {}
    included_tags = model.get('included_tags')
    tag_biases = {
        tag: int(bias)
        for tag, bias in raw_tag_biases.items()
        if bias in TAG_BIAS_FACTORS
        and bias != 0
        and (included_tags is None or tag in included_tags)
    }
    return {
        'tag_biases': tag_biases,
        'bpm_bias': clamp_bpm_bias(
            tuning.get('bpm_bias', DEFAULT_BPM_BIAS)
        ),
    }


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
    except (OverflowError, TypeError, ValueError):
        return None


def bucket_bpm(bpm, band_size=DEFAULT_BPM_BAND_SIZE):
    if bpm is None:
        return None
    if band_size <= 0:
        return bpm
    return bpm - (bpm % band_size)


def track_features(
    track,
    get_track_groups,
    bpm_band_size=DEFAULT_BPM_BAND_SIZE,
    included_tags=None,
):
    groups = get_track_groups(track) or []
    if included_tags is not None:
        groups = set(groups) & set(included_tags)
    return (
        tuple(sorted(groups)),
        bucket_bpm(_get_track_bpm(track), bpm_band_size),
    )


def make_track_summary(
    track,
    get_track_groups,
    bpm_band_size=DEFAULT_BPM_BAND_SIZE,
    included_tags=None,
):
    features = track_features(
        track, get_track_groups, bpm_band_size, included_tags
    )
    return {
        'groups': features[0],
        'bpm_band': features[1],
        'title': _get_track_display(track, 'title'),
        'artist': _get_track_display(track, 'artist'),
    }


def make_candidate_features(
    tracks,
    get_track_groups,
    bpm_band_size=DEFAULT_BPM_BAND_SIZE,
    included_tags=None,
):
    """Build the runtime feature lookup used to score candidate tracks."""
    candidates = {}
    for track in tracks:
        loc = _get_track_location(track)
        if loc is not None and loc not in candidates:
            candidates[loc] = make_track_summary(
                track, get_track_groups, bpm_band_size, included_tags
            )
    return candidates


def _get_track_display(track, tag):
    try:
        return track.get_tag_display(tag)
    except Exception:
        return ''


def get_playlist_tags(playlists, get_track_groups):
    tags = set()
    for playlist in playlists:
        for track in playlist:
            tags.update(get_track_groups(track) or [])
    return tags


def build_model(
    playlists,
    get_track_groups,
    bpm_band_size=DEFAULT_BPM_BAND_SIZE,
    included_tags=None,
):
    included_tags = None if included_tags is None else set(included_tags)
    transition_counts = defaultdict(Counter)
    candidate_features = {}
    playlist_count = 0
    track_count = 0

    for playlist in playlists:
        tracks = list(playlist)
        playlist_count += 1
        track_count += len(tracks)

        feature_cache = [
            track_features(
                track, get_track_groups, bpm_band_size, included_tags
            )
            for track in tracks
        ]

        for track in tracks:
            loc = _get_track_location(track)
            if loc is not None and loc not in candidate_features:
                candidate_features[loc] = make_track_summary(
                    track, get_track_groups, bpm_band_size, included_tags
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
        'included_tags': (
            None if included_tags is None else sorted(included_tags)
        ),
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
    candidate_features=None,
):
    return [
        location
        for location, _score in get_scored_suggestion_locations(
            model,
            previous_tracks,
            get_track_groups,
            max_suggestions,
            excluded_locations,
            candidate_features,
        )
    ]


def get_scored_suggestion_locations(
    model,
    previous_tracks,
    get_track_groups,
    max_suggestions=DEFAULT_MAX_SUGGESTIONS,
    excluded_locations=None,
    candidate_features=None,
):
    if model.get('version') != MODEL_VERSION:
        raise ValueError("Unsupported queue predictor model version")

    if len(previous_tracks) < 1:
        return []

    bpm_band_size = model.get('bpm_band_size', DEFAULT_BPM_BAND_SIZE)
    included_tags = model.get('included_tags')
    context = tuple(
        track_features(track, get_track_groups, bpm_band_size, included_tags)
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
    counts.update(
        _get_similar_candidate_counts(model, context[-1], candidate_features)
    )
    counts = apply_tag_biases(
        counts,
        candidate_features or model.get('candidate_features', {}),
        model.get('tag_biases', {}),
    )
    counts = apply_bpm_bias(
        counts,
        candidate_features or model.get('candidate_features', {}),
        context[-1][1],
        model.get('bpm_bias', DEFAULT_BPM_BIAS),
    )

    seen = set()
    previous_locations = {_get_track_location(track) for track in previous_tracks}
    previous_locations.discard(None)
    excluded_locations = set(excluded_locations or [])
    if len(context) > 1:
        excluded_locations.update(transition_counts.get(context, {}).keys())
    suggestions = []

    for loc, score in _rank_counts(counts):
        if candidate_features is not None and loc not in candidate_features:
            continue
        if loc in excluded_locations:
            continue
        if loc in previous_locations:
            continue
        if loc in seen:
            continue
        seen.add(loc)
        suggestions.append((loc, score))
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


def apply_tag_biases(counts, candidate_features, tag_biases):
    """Apply bounded, non-stacking tag preferences to candidate scores."""
    if not tag_biases:
        return counts

    adjusted = Counter()
    for location, score in counts.items():
        groups = candidate_features.get(location, {}).get('groups') or ()
        factors = [
            TAG_BIAS_FACTORS.get(tag_biases.get(tag), 1.0)
            for tag in groups
            if tag_biases.get(tag) in TAG_BIAS_FACTORS
            and tag_biases.get(tag) != 0
        ]
        if factors:
            # A geometric mean lets opposing preferences balance each other and
            # prevents tracks with many tags from receiving an accidental boost.
            factor = math.prod(factors) ** (1.0 / len(factors))
            score *= factor
        adjusted[location] = score
    return adjusted


def clamp_bpm_bias(bias):
    try:
        bias = int(round(float(bias)))
    except (OverflowError, TypeError, ValueError):
        return DEFAULT_BPM_BIAS
    return max(
        -BPM_BIAS_FULL_EFFECT_DELTA,
        min(BPM_BIAS_FULL_EFFECT_DELTA, bias),
    )


def apply_bpm_bias(counts, candidate_features, reference_bpm, bpm_bias):
    """Favor bounded tempo movement relative to the latest track."""
    bpm_bias = clamp_bpm_bias(bpm_bias)
    if bpm_bias == 0 or reference_bpm is None:
        return counts

    adjusted = Counter()
    requested_delta = abs(float(bpm_bias))
    requested_direction = 1.0 if bpm_bias > 0 else -1.0
    for location, score in counts.items():
        candidate_bpm = candidate_features.get(location, {}).get('bpm_band')
        if candidate_bpm is not None:
            directional_delta = (
                float(candidate_bpm - reference_bpm) * requested_direction
            )
            effect_delta = max(
                -requested_delta,
                min(requested_delta, directional_delta),
            )
            # The selected BPM amount caps the directional effect. At the
            # 30 BPM endpoint this ranges from 0.5x to 2x.
            score *= 2.0 ** (effect_delta / BPM_BIAS_FULL_EFFECT_DELTA)
        adjusted[location] = score
    return adjusted


def _get_similar_candidate_counts(
    model, last_feature, candidate_features=None
):
    use_all_candidates = candidate_features is not None
    if candidate_features is None:
        candidate_features = model.get('candidate_features', {})
    global_counts = Counter()
    for candidates in model.get('transition_counts', {}).values():
        global_counts.update(candidates)

    counts = Counter()
    candidate_locations = (
        candidate_features if use_all_candidates else global_counts
    )
    for loc in candidate_locations:
        features = candidate_features.get(loc)
        if features is None:
            continue
        score = _candidate_similarity_score(last_feature, features)
        if score > 0:
            counts[loc] = (score * 1000) + global_counts.get(loc, 0)
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


def rerank_suggestions_for_diversity(
    model,
    scored_locations,
    previous_tracks,
    get_track_groups,
    max_suggestions=DEFAULT_MAX_SUGGESTIONS,
    diversity=DEFAULT_DIVERSITY,
    candidate_features=None,
):
    candidates = list(scored_locations)
    if diversity <= 0:
        return candidates[:max_suggestions]
    if not candidates:
        return []

    strength = min(float(diversity), 100.0) / 100.0
    if candidate_features is None:
        candidate_features = model.get('candidate_features', {})
    bpm_band_size = model.get('bpm_band_size', DEFAULT_BPM_BAND_SIZE)
    included_tags = model.get('included_tags')
    recent_features = [
        make_track_summary(
            track, get_track_groups, bpm_band_size, included_tags
        )
        for track in previous_tracks
    ]
    highest_score = max(score for location, score in candidates) or 1
    selected = []

    while candidates and len(selected) < max_suggestions:
        best = max(
            candidates,
            key=lambda candidate: _diverse_candidate_score(
                candidate,
                candidate_features,
                recent_features,
                selected,
                highest_score,
                strength,
            ),
        )
        candidates.remove(best)
        selected.append(best)

    return selected


def _diverse_candidate_score(
    candidate,
    candidate_features,
    recent_features,
    selected,
    highest_score,
    strength,
):
    location, prediction_score = candidate
    features = candidate_features.get(location, {})
    relevance = float(prediction_score) / highest_score

    if recent_features:
        weights = list(range(1, len(recent_features) + 1))
        recent_similarity = sum(
            _summary_similarity(features, recent) * weight
            for recent, weight in zip(recent_features, weights)
        ) / sum(weights)
    else:
        recent_similarity = 0.0

    selected_similarity = max(
        (
            _summary_similarity(features, candidate_features.get(selected_loc, {}))
            for selected_loc, score in selected
        ),
        default=0.0,
    )
    novelty = 1.0 - ((recent_similarity * 0.65) + (selected_similarity * 0.35))
    return ((1.0 - strength) * relevance) + (strength * novelty)


def _summary_similarity(first, second):
    first_groups = set(first.get('groups') or ())
    second_groups = set(second.get('groups') or ())
    all_groups = first_groups | second_groups
    group_similarity = (
        float(len(first_groups & second_groups)) / len(all_groups)
        if all_groups
        else 0.0
    )

    first_artist = first.get('artist') or ''
    second_artist = second.get('artist') or ''
    artist_similarity = float(bool(first_artist and first_artist == second_artist))

    first_bpm = first.get('bpm_band')
    second_bpm = second.get('bpm_band')
    if first_bpm is None or second_bpm is None:
        bpm_similarity = 0.0
    else:
        bpm_similarity = max(0.0, 1.0 - (abs(first_bpm - second_bpm) / 30.0))

    return (
        (group_similarity * 0.55)
        + (artist_similarity * 0.25)
        + (bpm_similarity * 0.20)
    )


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


def resolve_scored_suggestion_tracks(
    collection, scored_locations, max_suggestions=DEFAULT_MAX_SUGGESTIONS
):
    tracks = []
    for loc, score in scored_locations:
        track = collection.get_track_by_loc(loc)
        if track is not None:
            tracks.append((track, score))
        if len(tracks) >= max_suggestions:
            break
    return tracks
