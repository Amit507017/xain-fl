from typing import List, Tuple

from numpy import ndarray

# Returned from keras
KerasDataset = Tuple[Tuple[ndarray, ndarray], Tuple[ndarray, ndarray]]

# User in the autofl project
FederatedDatasetSplit = Tuple[ndarray, ndarray]
FederatedDataset = Tuple[List[FederatedDatasetSplit], FederatedDatasetSplit]

FnameNDArrayTuple = Tuple[str, ndarray]
