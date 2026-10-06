"""Selecao, avaliacao e ajuste das variaveis sem acesso a I/O."""
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real

import numpy as np

try:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import ElasticNet, HuberRegressor, Lasso, Ridge
    import warnings
except Exception:  # pragma: no cover - fallback para ambientes sem sklearn.
    ConvergenceWarning = None
    ElasticNet = HuberRegressor = Lasso = Ridge = None
    warnings = None

from midas_core.domain.features import FEATURE_NAMES
from midas_core.domain.regression import (
    RidgeModel,
    directional_accuracy,
    fit,
    mean_absolute_error,
    predict,
    rank_correlation,
    temporal_partitions,
)

@dataclass(frozen=True)
class VariableTrainingConfig:
    feature_names: tuple[str, ...] = FEATURE_NAMES
    alpha_candidates: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0)
    lasso_alpha_candidates: tuple[float, ...] = (0.0005, 0.001, 0.005, 0.01)
    elasticnet_alpha_candidates: tuple[float, ...] = (0.0005, 0.001, 0.005, 0.01)
    elasticnet_l1_ratio_candidates: tuple[float, ...] = (0.25, 0.5, 0.75)
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    minimum_selection_samples: int = 20
    minimum_validation_samples: int = 5
    minimum_evaluation_samples: int = 20
    minimum_test_samples: int = 5
    model_version: int = 3
    use_sklearn: bool = True

@dataclass(frozen=True)
class TrainingResult:
    model: RidgeModel
    metrics: dict
    parameters: dict

@dataclass(frozen=True)
class ModelCandidate:
    algorithm: str
    parameters: dict

class VariableTrainer:
    """Treina as variaveis e devolve um resultado serializavel pelo chamador."""

    def __init__(self, config=None):
        self.config = config or VariableTrainingConfig()

    def train(self, rows, now=None):
        if not rows:
            raise ValueError("Dataset sem amostras.")
        now = now or datetime.now(timezone.utc)
        self._validate(rows, now)
        partitions = temporal_partitions(
            rows,
            validation_fraction=self.config.validation_fraction,
            test_fraction=self.config.test_fraction,
        )
        self._validate_partition_sizes(partitions)

        selected, selection_results = self._select_model(
            partitions.selection_train,
            partitions.validation,
        )
        evaluation_features, evaluation_targets = self._arrays(partitions.evaluation_train)
        test_features, test_targets = self._arrays(partitions.test)
        evaluation_model = self._fit_candidate(evaluation_features, evaluation_targets, selected)
        test_estimates = predict(evaluation_model, test_features)
        residuals = test_targets - test_estimates
        baseline = float(np.mean(evaluation_targets))

        metrics = {
            "mae": mean_absolute_error(test_targets, test_estimates),
            "baseline_mae": mean_absolute_error(
                test_targets, np.full(len(test_targets), baseline)
            ),
            "directional_accuracy": directional_accuracy(test_targets, test_estimates),
            "rank_correlation": rank_correlation(
                partitions.test, test_targets, test_estimates
            ),
            "train": len(evaluation_targets),
            "validation": len(partitions.validation),
            "test": len(test_targets),
            "selected_model": selected.algorithm,
        }
        metrics["mae_improvement"] = (
            metrics["baseline_mae"] - metrics["mae"]
        ) / metrics["baseline_mae"]
        metrics["predictions"] = [
            {
                "ticker": row["ticker"],
                "as_of": row["as_of"].isoformat(),
                "label_end": row["label_end"].isoformat(),
                "predicted": float(estimated),
                "actual": float(actual),
                "absolute_error": float(abs(actual - estimated)),
            }
            for row, estimated, actual in zip(
                partitions.test, test_estimates, test_targets
            )
        ]
        float_metrics = [value for value in metrics.values() if isinstance(value, float)]
        if not all(np.isfinite(value) for value in float_metrics):
            raise ValueError("Treinamento produziu metricas invalidas.")

        all_features, all_targets = self._arrays(rows)
        production_model = self._fit_candidate(all_features, all_targets, selected)
        parameters = {
            "model_version": self.config.model_version,
            "features": list(self.config.feature_names),
            "algorithm": selected.algorithm,
            "algorithm_parameters": selected.parameters,
            "alpha": selected.parameters.get("alpha"),
            "alpha_candidates": list(self.config.alpha_candidates),
            "validation_start": partitions.validation_start.isoformat(),
            "test_start": partitions.test_start.isoformat(),
            "selection_results": selection_results,
            "residual_quantiles": {
                "p10": float(np.quantile(residuals, 0.10)),
                "p90": float(np.quantile(residuals, 0.90)),
            },
            "sklearn_enabled": self._sklearn_available(),
        }
        return TrainingResult(production_model, metrics, parameters)

    def _validate(self, rows, now):
        for row in rows:
            if not row["as_of"] < row["label_end"] <= now:
                raise ValueError("Amostra com datas invalidas ou resultado futuro.")
            try:
                values = [
                    row["features"][name] for name in self.config.feature_names
                ] + [row["target"]]
            except KeyError as error:
                raise ValueError(f"Variavel ausente: {error.args[0]}.") from error
            if not all(isinstance(value, Real) and np.isfinite(value) for value in values):
                raise ValueError("Amostra com valores invalidos.")

    def _arrays(self, rows):
        features = np.asarray(
            [
                [row["features"][name] for name in self.config.feature_names]
                for row in rows
            ],
            dtype=float,
        )
        targets = np.asarray([row["target"] for row in rows], dtype=float)
        return features, targets

    def _select_model(self, training_rows, validation_rows):
        training_features, training_targets = self._arrays(training_rows)
        validation_features, validation_targets = self._arrays(validation_rows)
        results = []
        for candidate in self._candidates():
            model = self._fit_candidate(training_features, training_targets, candidate)
            estimates = predict(model, validation_features)
            error = mean_absolute_error(validation_targets, estimates)
            results.append({
                "algorithm": candidate.algorithm,
                "parameters": candidate.parameters,
                "mae": error,
            })
        selected_result = min(
            results,
            key=lambda result: (
                result["mae"],
                result["algorithm"],
                repr(sorted(result["parameters"].items())),
            ),
        )
        selected = ModelCandidate(
            selected_result["algorithm"],
            selected_result["parameters"],
        )
        return selected, results

    def _candidates(self):
        candidates = [
            ModelCandidate("ridge_numpy", {"alpha": alpha})
            for alpha in self.config.alpha_candidates
        ]
        if not self._sklearn_available():
            return candidates
        candidates.extend(
            ModelCandidate("ridge_sklearn", {"alpha": alpha})
            for alpha in self.config.alpha_candidates
        )
        candidates.extend(
            ModelCandidate("lasso_sklearn", {"alpha": alpha})
            for alpha in self.config.lasso_alpha_candidates
        )
        for alpha in self.config.elasticnet_alpha_candidates:
            for l1_ratio in self.config.elasticnet_l1_ratio_candidates:
                candidates.append(ModelCandidate(
                    "elasticnet_sklearn",
                    {"alpha": alpha, "l1_ratio": l1_ratio},
                ))
        candidates.append(ModelCandidate("huber_sklearn", {"epsilon": 1.35, "alpha": 0.0001}))
        return candidates

    def _fit_candidate(self, features, targets, candidate):
        if candidate.algorithm == "ridge_numpy":
            return fit(features, targets, candidate.parameters["alpha"])
        if not self._sklearn_available():
            raise ValueError(f"Modelo indisponivel sem scikit-learn: {candidate.algorithm}.")
        mean, scale, standardized = self._standardize(features)
        estimator = self._estimator(candidate)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            estimator.fit(standardized, targets)
        weights = np.concatenate([[float(estimator.intercept_)], np.asarray(estimator.coef_, dtype=float)])
        return RidgeModel(mean, scale, weights)

    def _estimator(self, candidate):
        params = candidate.parameters
        if candidate.algorithm == "ridge_sklearn":
            return Ridge(alpha=params["alpha"], random_state=42)
        if candidate.algorithm == "lasso_sklearn":
            return Lasso(alpha=params["alpha"], max_iter=10000, random_state=42)
        if candidate.algorithm == "elasticnet_sklearn":
            return ElasticNet(
                alpha=params["alpha"],
                l1_ratio=params["l1_ratio"],
                max_iter=10000,
                random_state=42,
            )
        if candidate.algorithm == "huber_sklearn":
            return HuberRegressor(alpha=params["alpha"], epsilon=params["epsilon"])
        raise ValueError(f"Modelo desconhecido: {candidate.algorithm}.")

    def _standardize(self, features):
        mean = features.mean(axis=0)
        scale = features.std(axis=0)
        scale[scale < 1e-12] = 1
        return mean, scale, (features - mean) / scale

    def _sklearn_available(self):
        return self.config.use_sklearn and Ridge is not None

    def _validate_partition_sizes(self, partitions):
        requirements = (
            ("Treino para selecao", len(partitions.selection_train), self.config.minimum_selection_samples),
            ("Validacao", len(partitions.validation), self.config.minimum_validation_samples),
            ("Treino para avaliacao", len(partitions.evaluation_train), self.config.minimum_evaluation_samples),
            ("Teste temporal", len(partitions.test), self.config.minimum_test_samples),
        )
        for label, size, minimum in requirements:
            if size < minimum:
                raise ValueError(f"{label} insuficiente: {size}; minimo {minimum}.")
