"""Treina o modelo usando apenas XGBoost (sem ensemble)."""
from midas_core.application.datasets import publish_dataset
from midas_core.application.training import train
from midas_core.training import VariableTrainingConfig, VariableTrainer

# Configuração para usar apenas XGBoost
config = VariableTrainingConfig(
    use_ensemble=False,  # Desabilitar ensemble
    use_sklearn=True,
)

print("Treinando com XGBoost puro (sem ensemble)...")
dataset_id, sample_count = publish_dataset((12,), source='yahoo.finance')
print(f"Dataset: {dataset_id} ({sample_count} amostras)")

# Treinar com configuração personalizada
from midas_core.infrastructure.repositories import MongoRepository, PostgresRepository
from datetime import datetime, timezone
import uuid

mongo = MongoRepository()
pg = PostgresRepository()

rows = mongo.training_samples(dataset_id, 12)
if not rows:
    print("Erro: sem amostras")
    exit(1)

trainer = VariableTrainer(config=config)
result = trainer.train(rows)

print(f"Modelo selecionado: {result.parameters['algorithm']}")
print(f"MAE: {result.metrics['mae']:.4f}")
print(f"MAE ref: {result.metrics['baseline_mae']:.4f}")
imp = result.metrics['mae_improvement']
print(f"Melhora: {imp:.4f} ({imp*100:.1f}%)")
print(f"Acurácia: {result.metrics['directional_accuracy']:.4f} ({result.metrics['directional_accuracy']*100:.1f}%)")
print(f"Rank: {result.metrics['rank_correlation']:.4f}")

# Salvar resultado
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
mongo.save_artifact(artifact)
pg.save_model_run({
    "id": run_id,
    "dataset_id": dataset_id,
    "algorithm": result.parameters.get("algorithm", "xgboost_pure"),
    "horizon": 12,
    "metrics": result.metrics,
    "parameters": result.parameters,
})
print(f"Modelo salvo: {run_id}")