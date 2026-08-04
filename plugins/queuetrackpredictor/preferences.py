# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

import os

from xl.nls import gettext as _
from xlgui.preferences import widgets


name = _('Queue Track Predictor')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'preferences.ui')

MAX_SUGGESTIONS_OPTION = 'plugin/queuetrackpredictor/max_suggestions'
DEFAULT_MAX_SUGGESTIONS = 10
DIVERSITY_OPTION = 'plugin/queuetrackpredictor/diversity'
DEFAULT_DIVERSITY = 50
EXCLUDED_TAGS_OPTION = 'plugin/queuetrackpredictor/excluded_tags'
LAST_MODEL_OPTION = 'plugin/queuetrackpredictor/last_model'
TAG_BIASES_OPTION = 'plugin/queuetrackpredictor/tag_biases'
BPM_BIAS_OPTION = 'plugin/queuetrackpredictor/bpm_bias'
SUGGESTION_SOURCE_OPTION = 'plugin/queuetrackpredictor/suggestion_source'


class MaxSuggestionsPreference(widgets.SpinPreference):
    default = DEFAULT_MAX_SUGGESTIONS
    name = MAX_SUGGESTIONS_OPTION


class DiversityPreference(widgets.SpinPreference):
    default = DEFAULT_DIVERSITY
    name = DIVERSITY_OPTION
