import matplotlib.pyplot as plt
import numpy as np
import pytest
import tensorflow as tf

from . import data

assert_equal = np.testing.assert_equal
assert_raises = np.testing.assert_raises


@pytest.mark.integration
def test_load():
    (x_train, y_train), (x_test, y_test) = data.load(tf.keras.datasets.mnist)
    assert x_train.shape[0] == y_train.shape[0]
    assert x_test.shape[0] == y_test.shape[0]
    assert len(x_train.shape) == len(x_test.shape)
    assert len(y_train.shape) == len(y_test.shape)


def test_split_num_splits_valid_max():
    # Prepare
    x = np.zeros((3, 28, 28))
    y = np.zeros((3))
    num_splits = 3
    # Execute
    x_splits, y_splits = data.split(x, y, num_splits)
    # Assert
    assert len(x_splits) == num_splits
    assert len(y_splits) == num_splits
    # By the transitive property of == also:
    # len(x_splits) == len(y_splits)


def test_split_num_splits_valid_min():
    # Prepare
    x = np.zeros((3, 28, 28))
    y = np.zeros((3))
    num_splits = 1
    # Execute
    x_splits, y_splits = data.split(x, y, num_splits)
    # Assert
    assert len(x_splits) == num_splits
    assert len(y_splits) == num_splits
    # By the transitive property of == also:
    # len(x_splits) == len(y_splits)


def test_split_num_splits_valid():
    # Prepare
    x = np.zeros((6, 28, 28))
    y = np.zeros((6))
    num_splits = 2
    # Execute
    x_splits, y_splits = data.split(x, y, num_splits)
    # Assert
    assert len(x_splits) == num_splits
    assert len(y_splits) == num_splits
    # By the transitive property of == also:
    # len(x_splits) == len(y_splits)


def test_split_num_splits_invalid():
    # Prepare
    x = np.zeros((3, 28, 28))
    y = np.zeros((3))
    num_splits = 2
    # Execute & assert
    try:
        _, _ = data.split(x, y, num_splits)
        pytest.fail()
    except ValueError:
        pass


def test_split_dims():
    # Prepare
    x = np.zeros((3, 28, 28))
    y = np.zeros((3))
    num_splits = 3
    # Execute
    x_splits, y_splits = data.split(x, y, num_splits)
    # Assert: Corresponding x and y have the same number of examples
    for xs, ys in zip(x_splits, y_splits):
        assert xs.shape[0] == ys.shape[0]

    # Assert: Each split has the same dimensionality (except for number of examples)
    assert all([xs.shape == x_splits[0].shape for i, xs in enumerate(x_splits)])
    assert all([ys.shape == y_splits[0].shape for i, ys in enumerate(y_splits)])


def test_random_shuffle():
    # Prepare
    x = np.array([1, 2, 3, 4])
    y = np.array([11, 12, 13, 14])
    # Execute
    xs, ys = data.random_shuffle(x, y)
    # Assert
    for x, y in zip(xs, ys):
        assert x == (y - 10)


def test_balanced_labels_shuffle_wrong_section_count():
    # Prepare
    examples = range(100, 200)
    sorted_labels = range(10)

    x = np.array(examples, dtype=np.int64)
    y = np.tile(np.array(sorted_labels, dtype=np.int64), 10)

    with pytest.raises(Exception):
        data.balanced_labels_shuffle(x, y, section_count=3)


# We will test for an example count of 100 so section_count needs to
# be chosen so that "example_count / section_count" has no rest
@pytest.mark.parametrize(
    "section_count, example_count", [(2, 1000), (5, 1000), (10, 1000)]
)
def test_balanced_labels_shuffle(section_count, example_count):
    # Prepare
    unique_labels = range(10)  # 10 unique labels
    label_count = len(unique_labels)

    # Values will at the same time be their original labels
    # We will later use this for asserting if the label relationship is still present
    x = np.tile(np.array(unique_labels, dtype=np.int64), example_count // label_count)
    y = np.tile(np.array(unique_labels, dtype=np.int64), example_count // label_count)

    assert x.shape[0] == y.shape[0]

    # Execute
    x_shuffled, y_shuffled = data.balanced_labels_shuffle(
        x, y, section_count=section_count
    )

    # Assert
    # Create tuples for x,y splits so we can more easily analyze them
    x_splits = np.split(x_shuffled, indices_or_sections=section_count, axis=0)
    y_splits = np.split(y_shuffled, indices_or_sections=section_count, axis=0)

    for index, y_split in enumerate(y_splits):
        # Check that the split has the right size
        assert y_split.shape[0] == int(example_count / section_count)
        # Check that each segment contains each label
        assert set(y_split) == set(unique_labels)

        # Check that each y_split is uniquely shuffled
        if index > 0:
            with pytest.raises(Exception):
                assert_equal(
                    y_split,
                    y_splits[0],
                    err_msg="Each split should be uniquely shuffled",
                )

    # Check that each value still matches its label
    for x_split, y_split in zip(x_splits, y_splits):
        for x_i, y_i in zip(x_split, y_split):
            assert x_i == y_i
