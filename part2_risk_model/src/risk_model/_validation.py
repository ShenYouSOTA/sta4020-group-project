"""Shared numerical checks; tolerances scale with float64 matrix magnitude."""

import numpy as np


def _array(value, ndim, name):
    array = np.asarray(value, dtype=float)
    if array.ndim != ndim or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite {ndim}-dimensional array")
    return array


def _history(value, name="returns"):
    array = _array(value, 2, name)
    if array.shape[0] < 2 or array.shape[1] == 0:
        raise ValueError(f"{name} needs at least two observations and one series")
    return array


def _tolerance(matrix):
    scale = max(np.linalg.norm(matrix, ord=np.inf), np.finfo(float).tiny)
    return 100 * np.finfo(float).eps * max(len(matrix), 1) * scale


def _covariance(value, name="covariance"):
    matrix = _array(value, 2, name)
    if not len(matrix) or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} must be a nonempty square matrix")
    tolerance = _tolerance(matrix)
    if np.max(np.abs(matrix - matrix.T)) > tolerance:
        raise ValueError(f"{name} must be symmetric")
    matrix = (matrix + matrix.T) / 2
    if np.linalg.eigvalsh(matrix)[0] < -tolerance:
        raise ValueError(f"{name} must be positive semidefinite")
    return matrix


def _number(value, name, minimum=None, maximum=None):
    if np.ndim(value) != 0 or isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite scalar")
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return number


def _ids(values, name, allow_empty=False):
    ids = np.asarray(values)
    if ids.ndim != 1 or (not allow_empty and not len(ids)):
        raise ValueError(f"{name} must be a vector of identifiers")
    if len(np.unique(ids)) != len(ids):
        raise ValueError(f"{name} must contain unique identifiers")
    return ids


def _dates(values):
    dates = np.asarray(values, dtype="datetime64[ns]")
    if dates.ndim != 1 or not len(dates) or np.isnat(dates).any():
        raise ValueError("dates must be a nonempty vector of valid dates")
    if np.any(dates[1:] <= dates[:-1]):
        raise ValueError("dates must be strictly increasing")
    return dates
