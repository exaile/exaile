import pytest

from xl.common import MetadataList


@pytest.mark.parametrize(
    ('index', 'inserted_at'),
    [
        (0, 0),
        (2, 2),
        (3, 3),
        (100, 3),
        (-1, 2),
        (-100, 0),
    ],
)
def test_metadata_list_insert_preserves_metadata(index, inserted_at):
    items = MetadataList(['a', 'b', 'c'], ['A', 'B', 'C'])

    items.insert(index, 'new', 'NEW')

    expected_items = ['a', 'b', 'c']
    expected_items.insert(inserted_at, 'new')
    expected_metadata = ['A', 'B', 'C']
    expected_metadata.insert(inserted_at, 'NEW')
    assert list(items) == expected_items
    assert items.metadata == expected_metadata
