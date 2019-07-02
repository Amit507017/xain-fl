"""
Easily accessable datasets
"""

import tensorflow as tf

from autofl.data import data, persistence
from autofl.types import FederatedDataset

from .config import get_config

DATASET_NAME = 'cifar10_random_splits_10'


def generate_dataset() -> FederatedDataset:
    """Will generate dataset and store it locally"""
    return data.load_splits(10, tf.keras.datasets.cifar10)


def load_splits():
    return persistence.load_local_dataset(
        dataset_name=DATASET_NAME, local_datasets_dir=get_config("local_datasets_dir")
    )