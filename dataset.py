"""Compatibilidade: publicação e treinamento de snapshots."""
from midas_core.application.datasets import publish_dataset
from midas_core.interfaces.cli import dataset_main

if __name__ == "__main__":
    dataset_main()
