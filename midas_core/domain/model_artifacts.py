"""Contrato versionado de artefatos de modelo para serialização e inferência.

Famílias suportadas em produção:
- `ridge`: modelo linear serializável (mean, scale, weights).
- `ensemble_ridge`: média de dois ou mais modelos ridge serializáveis.

Famílias de árvore/deep não são elegíveis para produção até terem serialização
completa; a seleção pode avaliá-las, mas o artefato de inferência deve ser
serializável ou o run não é publicado.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ARTIFACT_SCHEMA_VERSION = 6
SUPPORTED_FAMILIES = frozenset({"ridge", "ensemble_ridge"})
PRODUCTION_ALGORITHMS = frozenset({
    "ridge",
    "ridge_sklearn",
    "lasso_sklearn",
    "elasticnet_sklearn",
    "huber_sklearn",
    "ensemble_ridge",
})


@dataclass(frozen=True)
class SerializedModel:
    family: str
    mean: list
    scale: list
    weights: list | None = None
    members: list | None = None


def is_serializable_family(algorithm):
    if algorithm in ("ensemble_ridge", "ensemble_boosted"):
        return True
    return algorithm in PRODUCTION_ALGORITHMS or algorithm == "ridge"


def serialize_ridge_model(model) -> dict:
    """Serializa um modelo linear (RidgeModel) no contrato versionado."""
    return {
        "family": "ridge",
        "mean": np.asarray(model.mean, dtype=float).tolist(),
        "scale": np.asarray(model.scale, dtype=float).tolist(),
        "weights": np.asarray(model.weights, dtype=float).tolist(),
    }


def serialize_ensemble(members) -> dict:
    """Serializa ensemble de modelos ridge. Exige pelo menos 2 membros."""
    if members is None or len(members) < 2:
        raise ValueError("Ensemble exige pelo menos dois modelos serializáveis.")
    payloads = []
    for member in members:
        payload = serialize_ridge_model(member)
        payloads.append(payload)
    return {
        "family": "ensemble_ridge",
        "members": payloads,
    }


def serialize_model(model, algorithm=None) -> dict:
    """Serializa o modelo de produção ou falha impedindo publicação."""
    if hasattr(model, "weights") and not hasattr(model, "estimator"):
        return serialize_ridge_model(model)
    if algorithm == "ensemble_ridge":
        raise ValueError("Ensemble deve ser serializado com serialize_ensemble.")
    raise ValueError(
        f"Modelo da família {type(model).__name__!r} não é serializável para produção."
    )


def validate_artifact(payload) -> dict:
    """Valida o contrato versionado; lança ValueError se inválido."""
    if not isinstance(payload, dict):
        raise ValueError("Artefato inválido.")
    family = payload.get("family")
    if family not in SUPPORTED_FAMILIES:
        raise ValueError("Família de modelo não suportada para inferência.")
    if family == "ridge":
        for key in ("mean", "scale", "weights"):
            values = payload.get(key)
            if not isinstance(values, list) or not values:
                raise ValueError(f"Artefato ridge sem {key}.")
        if len(payload["mean"]) != len(payload["scale"]):
            raise ValueError("Dimensões de mean/scale inconsistentes.")
    else:
        members = payload.get("members")
        if not isinstance(members, list) or len(members) < 2:
            raise ValueError("ensemble_ridge exige ao menos dois membros.")
        for member in members:
            validate_artifact({**member, "family": "ridge"})
    return payload


def from_artifact(artifact) -> "object":
    """Rehidrata modelo de inferência a partir do payload serializado.

    Aceita payload legado (mean/scale/weights sem family) como ridge.
    """
    from midas_core.domain.regression import RidgeModel, EnsembleRidgeModel

    payload = artifact.get("model") if isinstance(artifact, dict) and "model" in artifact else artifact
    if not isinstance(payload, dict):
        raise ValueError("Artefato inválido.")
    family = payload.get("family", "ridge" if "weights" in payload else None)
    if family is None and "weights" in payload:
        family = "ridge"
    if family == "ridge" or (family is None and "weights" in payload):
        validate_artifact({"family": "ridge", **{k: payload[k] for k in ("mean", "scale", "weights") if k in payload}})
        return RidgeModel(
            np.asarray(payload["mean"], dtype=float),
            np.asarray(payload["scale"], dtype=float),
            np.asarray(payload["weights"], dtype=float),
        )
    if family == "ensemble_ridge":
        validate_artifact(payload)
        members = [
            RidgeModel(
                np.asarray(m["mean"], dtype=float),
                np.asarray(m["scale"], dtype=float),
                np.asarray(m["weights"], dtype=float),
            )
            for m in payload["members"]
        ]
        return EnsembleRidgeModel(members)
    raise ValueError("Não foi possível rehidratar o artefato.")


def explain_linear(model, feature_names) -> dict:
    """Explicação de fatores do sinal para modelo linear."""
    weights = np.asarray(getattr(model, "weights", [0.0]), dtype=float)
    if weights.ndim == 0:
        weights = np.asarray([float(weights)])
    # weights[0] é intercepto; demais são fatores padronizados
    names = list(feature_names or [])
    contributions = []
    if len(weights) > 1:
        for index, name in enumerate(names[: len(weights) - 1]):
            contributions.append({
                "feature": name,
                "weight": float(weights[index + 1]),
            })
    contributions.sort(key=lambda item: abs(item["weight"]), reverse=True)
    return {
        "intercept": float(weights[0]) if len(weights) else 0.0,
        "factors": contributions,
        "method": "linear_weights_standardized",
    }
