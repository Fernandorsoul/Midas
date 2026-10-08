"""Caso de uso: carregar amostras, treinar variáveis e persistir resultado."""
from datetime import datetime, timezone
import uuid

from midas_core.domain.features import SUPPORTED_HORIZONS
from midas_core.domain.model_artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    serialize_ensemble,
    serialize_model,
    validate_artifact,
)
from midas_core.domain.regression import EnsembleRidgeModel
from midas_core.infrastructure.repositories import MongoRepository, PostgresRepository
from midas_core.training import VariableTrainer

def train(
    dataset_id,
    horizon,
    mongo_repository=None,
    postgres_repository=None,
    variable_trainer=None,
):
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError("Horizonte inválido.")
    mongo_repository = mongo_repository or MongoRepository()
    postgres_repository = postgres_repository or PostgresRepository()
    variable_trainer = variable_trainer or VariableTrainer()

    if not mongo_repository.dataset_exists(dataset_id):
        raise ValueError("Dataset real não encontrado.")
    rows = mongo_repository.training_samples(dataset_id, horizon)
    if not rows:
        raise ValueError("Dataset sem amostras para este horizonte.")

    result = variable_trainer.train(rows)
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Serialização é requisito de publicação: falha impede o run.
    if isinstance(result.model, EnsembleRidgeModel):
        model_payload = serialize_ensemble(result.model.members)
    else:
        model_payload = serialize_model(result.model, algorithm=result.parameters.get("algorithm"))
    validate_artifact(model_payload)

    parameters = dict(result.parameters)
    parameters["horizon_months"] = horizon
    parameters["artifact_schema_version"] = ARTIFACT_SCHEMA_VERSION

    artifact = {
        "_id": run_id,
        "dataset_id": dataset_id,
        "created_at": now,
        "parameters": parameters,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model": model_payload,
        # Campos legados para consumidores antigos (somente ridge)
        **{k: model_payload[k] for k in ("mean", "scale", "weights") if k in model_payload},
    }
    try:
        mongo_repository.save_artifact(artifact)
    except Exception as error:
        raise ValueError("Falha ao serializar/persistir o artefato do modelo.") from error
    try:
        postgres_repository.save_model_run({
            "id": run_id,
            "dataset_id": dataset_id,
            "algorithm": parameters.get("algorithm", "ridge"),
            "horizon": horizon,
            "metrics": result.metrics,
            "parameters": parameters,
        })
    except Exception:
        mongo_repository.delete_artifact(run_id)
        raise
    return run_id
