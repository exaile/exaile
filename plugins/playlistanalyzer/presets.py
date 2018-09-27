#
# Format is pretty simple. Provide the presets so that users
# can play around with 'proven' interesting visualizations
# without too much effort.
#
# Each preset is a tuple of (name, template_name, [tag_data])
# tag_data is currently a list of tag names
#

# TODO: add more interesting presets!

DEFAULT_PRESETS = [
    ('BPM Graph', 'force.tmpl.html', ['bpm']),
    ('BPM bar chart', 'bar_chart.tmpl.html', ['bpm']),
    ('GroupTagger bar chart', 'bar_chart.tmpl.html', ['__grouptagger']),
    ('Concept map Title/Genre', 'concept_map.tmpl.html', ['title', 'genre']),
    ('Concept map BPM/GroupTagger', 'concept_map.tmpl.html', ['bpm', '__grouptagger']),
]
