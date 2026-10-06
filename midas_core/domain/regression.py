"""Regressão Ridge e avaliação temporal, sem dependências externas."""
from dataclasses import dataclass

import numpy as np

@dataclass(frozen=True)
class RidgeModel:
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray

@dataclass(frozen=True)
class TemporalPartitions:
    selection_train: list
    validation: list
    evaluation_train: list
    test: list
    validation_start: object
    test_start: object

def temporal_split(rows, cutoff):
    training = [row for row in rows if row["label_end"] < cutoff]
    testing = [row for row in rows if row["as_of"] >= cutoff]
    return training, testing

def temporal_partitions(rows, validation_fraction=0.2, test_fraction=0.2):
    """Cria treino/validação/teste respeitando o fim de cada alvo."""
    dates = sorted({row["as_of"] for row in rows})
    if len(dates) < 15:
        raise ValueError("Poucas datas para separar treino, validação e teste.")
    validation_index = int(len(dates) * (1 - validation_fraction - test_fraction))
    test_index = int(len(dates) * (1 - test_fraction))
    validation_start = dates[validation_index]
    test_start = dates[test_index]
    return TemporalPartitions(
        selection_train=[row for row in rows if row["label_end"] < validation_start],
        validation=[row for row in rows if validation_start <= row["as_of"] < test_start and row["label_end"] < test_start],
        evaluation_train=[row for row in rows if row["label_end"] < test_start],
        test=[row for row in rows if row["as_of"] >= test_start],
        validation_start=validation_start,
        test_start=test_start,
    )

def fit(features, targets, alpha=10.0):
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale[scale < 1e-12] = 1
    design = np.column_stack([np.ones(len(features)), (features - mean) / scale])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0
    weights = np.linalg.solve(design.T @ design + penalty, design.T @ targets)
    return RidgeModel(mean, scale, weights)

def predict(model, features):
    values = np.atleast_2d(features)
    design = np.column_stack([np.ones(len(values)), (values - model.mean) / model.scale])
    return design @ model.weights

def mean_absolute_error(actual, estimated):
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(estimated))))

def directional_accuracy(actual, estimated):
    actual_sign = np.asarray(actual) > 0
    estimated_sign = np.asarray(estimated) > 0
    return float(np.mean(actual_sign == estimated_sign))

def _ranks(values):
    """Ranks médios, inclusive para empates."""
    values = np.asarray(values)
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    position = 0
    while position < len(values):
        end = position
        while end + 1 < len(values) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2
        ranks[order[position:end + 1]] = average
        position = end + 1
    return ranks

def rank_correlation(rows, actual, estimated):
    """Correlação de Spearman média entre ativos na mesma data."""
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(row["as_of"], []).append(index)
    correlations = []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        actual_ranks = _ranks([actual[index] for index in indices])
        estimated_ranks = _ranks([estimated[index] for index in indices])
        if np.std(actual_ranks) == 0 or np.std(estimated_ranks) == 0:
            continue
        correlations.append(float(np.corrcoef(actual_ranks, estimated_ranks)[0, 1]))
    return float(np.mean(correlations)) if correlations else 0.0

def from_artifact(artifact):
    return RidgeModel(
        np.asarray(artifact["mean"], dtype=float),
        np.asarray(artifact["scale"], dtype=float),
        np.asarray(artifact["weights"], dtype=float),
    )
