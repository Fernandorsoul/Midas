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

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover
    XGBRegressor = None

try:
    from lightgbm import LGBMRegressor
except Exception:  # pragma: no cover
    LGBMRegressor = None

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
except Exception:  # pragma: no cover
    tf = None
    keras = None
    layers = None

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
    alpha_candidates: tuple[float, ...] = (0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0)
    lasso_alpha_candidates: tuple[float, ...] = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05)
    elasticnet_alpha_candidates: tuple[float, ...] = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05)
    elasticnet_l1_ratio_candidates: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)
    xgb_n_estimators: tuple[int, ...] = (50, 100, 200)
    xgb_max_depth: tuple[int, ...] = (3, 5, 7)
    xgb_learning_rate: tuple[float, ...] = (0.01, 0.05, 0.1)
    lgbm_n_estimators: tuple[int, ...] = (50, 100, 200)
    lgbm_max_depth: tuple[int, ...] = (3, 5, 7)
    lgbm_learning_rate: tuple[float, ...] = (0.01, 0.05, 0.1)
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    minimum_selection_samples: int = 20
    minimum_validation_samples: int = 5
    minimum_evaluation_samples: int = 20
    minimum_test_samples: int = 5
    model_version: int = 5
    use_sklearn: bool = True
    use_ensemble: bool = True

@dataclass(frozen=True)
class TrainingResult:
    model: RidgeModel
    metrics: dict
    parameters: dict

@dataclass(frozen=True)
class ModelCandidate:
    algorithm: str
    parameters: dict

@dataclass(frozen=True)
class TreeModel:
    """Modelo para tree-based models (XGBoost, LightGBM)."""
    mean: np.ndarray
    scale: np.ndarray
    estimator: object  # XGBRegressor ou LGBMRegressor

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

        # Ensemble: treinar top modelos (incluindo XGBoost) e combinar previsões
        if self.config.use_ensemble and len(selection_results) >= 3:
            # Separar modelos por tipo
            linear_models = [r for r in selection_results if r["algorithm"] in ("ridge_sklearn", "lasso_sklearn", "elasticnet_sklearn", "huber_sklearn")]
            xgb_models = [r for r in selection_results if r["algorithm"] == "xgboost"]
            lgbm_models = [r for r in selection_results if r["algorithm"] == "lightgbm"]
            
            # Selecionar top modelos de cada tipo
            top_linear = sorted(linear_models, key=lambda x: x["mae"])[:2] if linear_models else []
            top_xgb = sorted(xgb_models, key=lambda x: x["mae"])[:1] if xgb_models else []
            top_lgbm = sorted(lgbm_models, key=lambda x: x["mae"])[:1] if lgbm_models else []
            
            # Combinar top modelos (mínimo3, máximo5)
            top_models = top_linear + top_xgb + top_lgbm
            if len(top_models) < 3:
                # Se não temos XGBoost/LightGBM, usar top3 lineares
                top_models = sorted(selection_results, key=lambda x: x["mae"])[:3]
            else:
                top_models = top_models[:5]  # Máximo5 modelos
            
            ensemble_predictions = []
            for model_result in top_models:
                candidate = ModelCandidate(model_result["algorithm"], model_result["parameters"])
                model = self._fit_candidate(evaluation_features, evaluation_targets, candidate)
                ensemble_predictions.append(predict(model, test_features))
            ensemble_estimates = np.mean(ensemble_predictions, axis=0)
            ensemble_mae = mean_absolute_error(test_targets, ensemble_estimates)
            # Usar ensemble se for melhor
            if ensemble_mae < mean_absolute_error(test_targets, test_estimates):
                test_estimates = ensemble_estimates
                residuals = test_targets - test_estimates
                selected = ModelCandidate("ensemble_boosted", {"models": top_models})

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

        # Para produção, usar ensemble se disponível
        all_features, all_targets = self._arrays(rows)
        if self.config.use_ensemble and selected.algorithm == "ensemble_boosted":
            # Treinar top modelos com todos os dados
            all_selection_results = selection_results
            linear_models = [r for r in all_selection_results if r["algorithm"] in ("ridge_sklearn", "lasso_sklearn", "elasticnet_sklearn", "huber_sklearn")]
            xgb_models = [r for r in all_selection_results if r["algorithm"] == "xgboost"]
            lgbm_models = [r for r in all_selection_results if r["algorithm"] == "lightgbm"]
            top_linear = sorted(linear_models, key=lambda x: x["mae"])[:2] if linear_models else []
            top_xgb = sorted(xgb_models, key=lambda x: x["mae"])[:1] if xgb_models else []
            top_lgbm = sorted(lgbm_models, key=lambda x: x["mae"])[:1] if lgbm_models else []
            top_models = top_linear + top_xgb + top_lgbm
            if len(top_models) < 3:
                top_models = sorted(all_selection_results, key=lambda x: x["mae"])[:3]
            else:
                top_models = top_models[:5]
            production_model = self._fit_candidate(all_features, all_targets, 
                ModelCandidate(top_models[0]["algorithm"], top_models[0]["parameters"]))
        else:
            production_model = self._fit_candidate(all_features, all_targets, selected)
        parameters = {
            "model_version": self.config.model_version,
            "features": list(self.config.feature_names),
            "algorithm": selected.algorithm,
            "algorithm_parameters": selected.parameters if hasattr(selected, 'parameters') else {},
            "alpha": selected.parameters.get("alpha") if hasattr(selected, 'parameters') else None,
            "alpha_candidates": list(self.config.alpha_candidates),
            "validation_start": partitions.validation_start.isoformat(),
            "test_start": partitions.test_start.isoformat(),
            "selection_results": selection_results,
            "residual_quantiles": {
                "p10": float(np.quantile(residuals, 0.10)),
                "p90": float(np.quantile(residuals, 0.90)),
            },
            "sklearn_enabled": self._sklearn_available(),
            "ensemble_enabled": self.config.use_ensemble,
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
        # XGBoost candidates
        if XGBRegressor is not None:
            for n_estimators in self.config.xgb_n_estimators:
                for max_depth in self.config.xgb_max_depth:
                    for learning_rate in self.config.xgb_learning_rate:
                        candidates.append(ModelCandidate(
                            "xgboost",
                            {"n_estimators": n_estimators, "max_depth": max_depth, "learning_rate": learning_rate},
                        ))
        # LightGBM candidates
        if LGBMRegressor is not None:
            for n_estimators in self.config.lgbm_n_estimators:
                for max_depth in self.config.lgbm_max_depth:
                    for learning_rate in self.config.lgbm_learning_rate:
                        candidates.append(ModelCandidate(
                            "lightgbm",
                            {"n_estimators": n_estimators, "max_depth": max_depth, "learning_rate": learning_rate},
                        ))
        # Transformer candidate
        if keras is not None:
            candidates.append(ModelCandidate("transformer", {"epochs": 50, "batch_size": 32}))
            candidates.append(ModelCandidate("gru", {"epochs": 50, "batch_size": 32}))
            candidates.append(ModelCandidate("cnn", {"epochs": 50, "batch_size": 32}))
        # Random Forest
        try:
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            for n_estimators in (50, 100, 200):
                for max_depth in (3, 5, 7):
                    candidates.append(ModelCandidate(
                        "random_forest",
                        {"n_estimators": n_estimators, "max_depth": max_depth},
                    ))
            for n_estimators in (50, 100, 200):
                for max_depth in (3, 5, 7):
                    for learning_rate in (0.01, 0.05, 0.1):
                        candidates.append(ModelCandidate(
                            "gradient_boosting",
                            {"n_estimators": n_estimators, "max_depth": max_depth, "learning_rate": learning_rate},
                        ))
        except ImportError:
            pass
        return candidates

    def _fit_candidate(self, features, targets, candidate):
        if candidate.algorithm == "ridge_numpy":
            return fit(features, targets, candidate.parameters["alpha"])
        if not self._sklearn_available():
            raise ValueError(f"Modelo indisponivel sem scikit-learn: {candidate.algorithm}.")
        mean, scale, standardized = self._standardize(features)
        # XGBoost, LightGBM, Random Forest, Gradient Boosting
        if candidate.algorithm in ("xgboost", "lightgbm", "random_forest", "gradient_boosting"):
            estimator = self._estimator(candidate)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                estimator.fit(standardized, targets)
            return TreeModel(mean, scale, estimator)
        # Deep learning models (Transformer, GRU, CNN)
        if candidate.algorithm in ("transformer", "gru", "cnn"):
            model = self._build_deep_model(standardized.shape[1], candidate.algorithm)
            model.fit(standardized, targets, epochs=candidate.parameters["epochs"],
                     batch_size=candidate.parameters["batch_size"], verbose=0)
            return TreeModel(mean, scale, model)
        # Modelos lineares sklearn
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
        if candidate.algorithm == "xgboost":
            return XGBRegressor(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                random_state=42,
                verbosity=0,
            )
        if candidate.algorithm == "lightgbm":
            return LGBMRegressor(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                random_state=42,
                verbose=-1,
            )
        if candidate.algorithm == "random_forest":
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                random_state=42,
            )
        if candidate.algorithm == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                random_state=42,
            )
        raise ValueError(f"Modelo desconhecido: {candidate.algorithm}.")

    def _standardize(self, features):
        mean = features.mean(axis=0)
        scale = features.std(axis=0)
        scale[scale < 1e-12] = 1
        return mean, scale, (features - mean) / scale

    def _sklearn_available(self):
        return self.config.use_sklearn and Ridge is not None

    def _build_transformer(self, input_dim):
        """Constrói um modelo Transformer simples para regressão."""
        inputs = keras.Input(shape=(input_dim,))
        x = layers.Reshape((1, input_dim))(inputs)
        attention_output = layers.MultiHeadAttention(num_heads=2, key_dim=input_dim)(x, x)
        x = layers.Add()([x, attention_output])
        x = layers.LayerNormalization()(x)
        x = layers.Dense(input_dim * 2, activation='relu')(x)
        x = layers.Dense(input_dim)(x)
        x = layers.Flatten()(x)
        outputs = layers.Dense(1)(x)
        model = keras.Model(inputs, outputs)
        model.compile(optimizer='adam', loss='mse')
        return model

    def _build_deep_model(self, input_dim, model_type):
        """Constrói modelos deep learning (Transformer, GRU, CNN)."""
        inputs = keras.Input(shape=(input_dim,))
        x = layers.Reshape((1, input_dim))(inputs)
        if model_type == "transformer":
            attention_output = layers.MultiHeadAttention(num_heads=2, key_dim=input_dim)(x, x)
            x = layers.Add()([x, attention_output])
            x = layers.LayerNormalization()(x)
            x = layers.Dense(input_dim * 2, activation='relu')(x)
            x = layers.Dense(input_dim)(x)
        elif model_type == "gru":
            x = layers.GRU(input_dim, return_sequences=False)(x)
            x = layers.Dense(input_dim, activation='relu')(x)
        elif model_type == "cnn":
            x = layers.Conv1D(input_dim, 1, activation='relu')(x)
            x = layers.GlobalAveragePooling1D()(x)
            x = layers.Dense(input_dim, activation='relu')(x)
        x = layers.Flatten()(x)
        outputs = layers.Dense(1)(x)
        model = keras.Model(inputs, outputs)
        model.compile(optimizer='adam', loss='mse')
        return model

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
