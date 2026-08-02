import importlib.util
import os


STORE_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    '..',
    'plugins',
    'queuetrackpredictor',
    'model_store.py',
)
SPEC = importlib.util.spec_from_file_location(
    'queuetrackpredictor_model_store', STORE_PATH
)
store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(store)


def test_catalog_operations_update_selection():
    catalog = store.empty_catalog()
    store.add_model(catalog, 'Party', {'track_count': 10})
    store.add_model(catalog, 'Quiet', {'track_count': 20})
    assert catalog['selected'] == 'Quiet'

    store.select_model(catalog, 'Party')
    store.rename_model(catalog, 'Party', 'Dance')
    assert catalog['selected'] == 'Dance'

    store.remove_model(catalog, 'Dance')
    assert catalog['selected'] == 'Quiet'


def test_replace_model_preserves_selection():
    catalog = store.empty_catalog()
    store.add_model(catalog, 'Selected', {'track_count': 10})
    store.add_model(catalog, 'Other', {'track_count': 20})
    store.select_model(catalog, 'Selected')

    store.replace_model(catalog, 'Other', {'track_count': 30})

    assert catalog['models']['Other']['track_count'] == 30
    assert catalog['selected'] == 'Selected'


def test_catalog_rejects_empty_and_duplicate_names():
    catalog = store.empty_catalog()
    store.add_model(catalog, 'Party', {})

    for name in ('', '  ', 'Party'):
        try:
            store.add_model(catalog, name, {})
        except ValueError:
            pass
        else:
            assert False, 'Expected invalid model name to fail'


def test_catalog_round_trip(tmp_path):
    path = str(tmp_path / 'models.pickle')
    catalog = store.empty_catalog()
    store.add_model(catalog, 'Road trip', {'track_count': 42})

    store.save_catalog(path, catalog)

    assert store.load_catalog(path) == catalog
