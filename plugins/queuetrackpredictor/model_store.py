# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

import os
import pickle
import tempfile


CATALOG_VERSION = 1


def empty_catalog():
    return {'version': CATALOG_VERSION, 'selected': None, 'models': {}}


def model_names(catalog):
    return sorted(catalog['models'], key=lambda name: (name.casefold(), name))


def load_catalog(path):
    try:
        with open(path, 'rb') as catalog_file:
            catalog = pickle.load(catalog_file)
    except IOError:
        catalog = empty_catalog()

    if catalog.get('version') != CATALOG_VERSION:
        raise ValueError('Unsupported queue predictor catalog version')
    if not isinstance(catalog.get('models'), dict):
        raise ValueError('Invalid queue predictor catalog')
    if catalog.get('selected') not in catalog['models']:
        catalog['selected'] = next(iter(model_names(catalog)), None)
    return catalog


def save_catalog(path, catalog):
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    temporary = tempfile.NamedTemporaryFile(dir=directory, delete=False)
    try:
        with temporary:
            pickle.dump(catalog, temporary, protocol=2)
        os.replace(temporary.name, path)
    except Exception:
        try:
            os.unlink(temporary.name)
        except OSError:
            pass
        raise


def add_model(catalog, name, model):
    name = _validated_name(name)
    if name in catalog['models']:
        raise ValueError('A model with that name already exists')
    catalog['models'][name] = model
    catalog['selected'] = name


def replace_model(catalog, name, model):
    if name not in catalog['models']:
        raise KeyError(name)
    catalog['models'][name] = model


def remove_model(catalog, name):
    if name not in catalog['models']:
        raise KeyError(name)
    del catalog['models'][name]
    if catalog.get('selected') == name:
        catalog['selected'] = next(iter(model_names(catalog)), None)


def rename_model(catalog, old_name, new_name):
    new_name = _validated_name(new_name)
    if old_name not in catalog['models']:
        raise KeyError(old_name)
    if new_name != old_name and new_name in catalog['models']:
        raise ValueError('A model with that name already exists')
    if new_name == old_name:
        return
    catalog['models'][new_name] = catalog['models'].pop(old_name)
    if catalog.get('selected') == old_name:
        catalog['selected'] = new_name


def select_model(catalog, name):
    if name not in catalog['models']:
        raise KeyError(name)
    catalog['selected'] = name


def _validated_name(name):
    name = name.strip()
    if not name:
        raise ValueError('Model name cannot be empty')
    return name
