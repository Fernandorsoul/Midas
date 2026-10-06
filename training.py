"""Compatibilidade: API pública de treinamento."""
from midas_core.application.training import train
from midas_core.domain.regression import fit, predict, temporal_split
from midas_core.interfaces.cli import training_main
from midas_core.training import VariableTrainer, VariableTrainingConfig

__all__ = [
    "VariableTrainer",
    "VariableTrainingConfig",
    "fit",
    "predict",
    "temporal_split",
    "train",
]

if __name__ == "__main__":
    training_main()
