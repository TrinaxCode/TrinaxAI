from collections import OrderedDict

import pytest

from app.services.engine_state import lru_get, lru_set


def test_lru_cache_evicts_least_recently_used_entry():
    cache = OrderedDict()
    lru_set(cache, ("a",), "A", max_entries=2)
    lru_set(cache, ("b",), "B", max_entries=2)

    assert lru_get(cache, ("a",)) == "A"
    lru_set(cache, ("c",), "C", max_entries=2)

    assert list(cache) == [("a",), ("c",)]
    assert lru_get(cache, ("b",)) is None


def test_lru_cache_rejects_unbounded_configuration():
    with pytest.raises(ValueError, match="positive"):
        lru_set(OrderedDict(), "key", "value", max_entries=0)
