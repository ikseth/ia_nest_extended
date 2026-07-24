import math

import pytest

from ianest_extended import FakeEmbedder, InvalidEmbeddingDimensionError


def test_fake_embedder_is_deterministic_and_normalized():
    embedder = FakeEmbedder(dimension=12)

    first = embedder.embed("mismo texto")
    second = embedder.embed("mismo texto")

    assert first == second
    assert len(first) == 12
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_fake_embedder_rejects_invalid_dimension():
    with pytest.raises(InvalidEmbeddingDimensionError):
        FakeEmbedder(dimension=0)
