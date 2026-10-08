import unittest
import numpy as np

from midas_core.domain.model_artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    explain_linear,
    from_artifact,
    serialize_ensemble,
    serialize_model,
    validate_artifact,
)
from midas_core.domain.regression import EnsembleRidgeModel, RidgeModel, predict


def ridge(weights, n_features=2):
    mean = np.zeros(n_features)
    scale = np.ones(n_features)
    return RidgeModel(mean, scale, np.asarray(weights, dtype=float))


class SerializeTests(unittest.TestCase):
    def test_serialize_ridge_round_trip(self):
        model = ridge([1.0, 0.5, -0.25])
        payload = serialize_model(model)
        self.assertEqual(payload["family"], "ridge")
        validate_artifact(payload)
        restored = from_artifact(payload)
        features = np.asarray([[0.1, 0.2]])
        np.testing.assert_allclose(predict(restored, features), predict(model, features))

    def test_legacy_artifact_without_family_loads_as_ridge(self):
        legacy = {
            "mean": [0.0, 0.0],
            "scale": [1.0, 1.0],
            "weights": [0.1, 0.2, 0.3],
        }
        model = from_artifact(legacy)
        self.assertIsInstance(model, RidgeModel)

    def test_ensemble_requires_two_members(self):
        with self.assertRaisesRegex(ValueError, "dois modelos"):
            serialize_ensemble([ridge([1.0, 0.1])])

    def test_ensemble_round_trip_predicts_average(self):
        m1 = ridge([0.0, 2.0, 0.0])
        m2 = ridge([0.0, 4.0, 0.0])
        payload = serialize_ensemble([m1, m2])
        self.assertEqual(payload["family"], "ensemble_ridge")
        self.assertEqual(len(payload["members"]), 2)
        restored = from_artifact(payload)
        self.assertIsInstance(restored, EnsembleRidgeModel)
        features = np.asarray([[1.0, 1.0]])
        # previsões: 2.0 e 4.0 → média 3.0
        np.testing.assert_allclose(predict(restored, features), np.asarray([3.0]))

    def test_ensemble_model_rejects_single_member(self):
        with self.assertRaisesRegex(ValueError, "dois modelos"):
            EnsembleRidgeModel((ridge([1.0, 0.1]),))

    def test_tree_like_model_not_serializable(self):
        class FakeTree:
            mean = np.zeros(1)
            scale = np.ones(1)
            estimator = object()

        with self.assertRaisesRegex(ValueError, "não é serializável"):
            serialize_model(FakeTree())

    def test_validate_rejects_unknown_family(self):
        with self.assertRaisesRegex(ValueError, "não suportada"):
            validate_artifact({"family": "deep_net", "weights": [1]})

    def test_explain_linear_orders_factors(self):
        model = ridge([0.5, -0.8, 0.2])
        explanation = explain_linear(model, ["momentum_12m", "volatility"])
        self.assertEqual(explanation["intercept"], 0.5)
        self.assertEqual(explanation["factors"][0]["feature"], "momentum_12m")
        self.assertEqual(explanation["factors"][0]["weight"], -0.8)


class TrainingSerializationTests(unittest.TestCase):
    def test_train_blocks_publication_when_not_serializable(self):
        from midas_core.application import training as training_module

        class BadModel:
            mean = np.zeros(1)
            scale = np.ones(1)
            estimator = object()

        class FakeTrainer:
            def train(self, rows):
                from midas_core.training import TrainingResult
                return TrainingResult(BadModel(), {"mae": 0.1}, {"algorithm": "xgboost"})

        class FakeMongo:
            def dataset_exists(self, dataset_id):
                return True

            def training_samples(self, dataset_id, horizon):
                return [{"as_of": 1, "label_end": 2, "features": {}, "target": 0.1}]

            def save_artifact(self, artifact):
                raise AssertionError("não deveria salvar artefato não serializável")

            def delete_artifact(self, artifact_id):
                pass

        class FakePg:
            def save_model_run(self, run):
                raise AssertionError("não deveria publicar run")

        with self.assertRaisesRegex(ValueError, "serializ"):
            training_module.train(
                "ds", 12,
                mongo_repository=FakeMongo(),
                postgres_repository=FakePg(),
                variable_trainer=FakeTrainer(),
            )

    def test_train_persists_versioned_ridge_artifact(self):
        from midas_core.application import training as training_module
        from midas_core.training import TrainingResult

        saved = {}

        class FakeTrainer:
            def train(self, rows):
                model = ridge([0.1, 0.2, 0.3])
                return TrainingResult(model, {"mae": 0.1}, {"algorithm": "ridge"})

        class FakeMongo:
            def dataset_exists(self, dataset_id):
                return True

            def training_samples(self, dataset_id, horizon):
                return [{"x": 1}]

            def save_artifact(self, artifact):
                saved["artifact"] = artifact

            def delete_artifact(self, artifact_id):
                pass

        class FakePg:
            def save_model_run(self, run):
                saved["run"] = run

        run_id = training_module.train(
            "ds", 12,
            mongo_repository=FakeMongo(),
            postgres_repository=FakePg(),
            variable_trainer=FakeTrainer(),
        )
        self.assertTrue(run_id)
        self.assertEqual(saved["artifact"]["schema_version"], ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(saved["artifact"]["model"]["family"], "ridge")
        self.assertEqual(saved["artifact"]["parameters"]["horizon_months"], 12)
        self.assertEqual(saved["run"]["algorithm"], "ridge")


if __name__ == "__main__":
    unittest.main()
