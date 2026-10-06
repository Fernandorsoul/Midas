"""Caso de uso: carregar amostras, treinar variáveis e persistir resultado."""
from datetime import datetime, timezone
import uuid

from midas_core.domain.features import SUPPORTED_HORIZONS
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
    artifact = {
        "_id": run_id,
        "dataset_id": dataset_id,
        "created_at": now,
        "parameters": result.parameters,
        "mean": result.model.mean.tolist(),
        "scale": result.model.scale.tolist(),
        "weights": result.model.weights.tolist(),
    }
    mongo_repository.save_artifact(artifact)
    try:
        postgres_repository.save_model_run({
            "id": run_id,
            "dataset_id": dataset_id,
            "algorithm": result.parameters.get("algorithm", "temporal-model-selection-v3"),
            "horizon": horizon,
            "metrics": result.metrics,
            "parameters": result.parameters,
        })
    except Exception:
        mongo_repository.delete_artifact(run_id)
        raise
    return run_id
