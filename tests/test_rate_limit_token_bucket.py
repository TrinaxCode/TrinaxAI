import app.security.rate_limit as rate_limit


def test_token_bucket_refills_monotonically(monkeypatch):
    clock = iter((10.0, 10.0, 10.0, 15.0))
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_MAX", 2)
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_WINDOW", 10.0)
    rate_limit.state.rate_limit_clients.clear()
    rate_limit.state.rate_limit_last_prune = 10.0

    assert rate_limit._check_rate_limit("client") is True
    assert rate_limit._check_rate_limit("client") is True
    assert rate_limit._check_rate_limit("client") is False
    assert rate_limit._check_rate_limit("client") is True


def test_token_bucket_client_table_is_bounded(monkeypatch):
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_MAX_CLIENTS", 2)
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100.0)
    rate_limit.state.rate_limit_clients.clear()
    rate_limit.state.rate_limit_last_prune = 100.0

    assert rate_limit._check_rate_limit("oldest") is True
    rate_limit.state.rate_limit_clients["oldest"] = (0.0, 1.0)
    assert rate_limit._check_rate_limit("newer") is True
    rate_limit.state.rate_limit_clients["newer"] = (0.0, 2.0)
    assert rate_limit._check_rate_limit("newest") is True

    assert "oldest" not in rate_limit.state.rate_limit_clients
    assert len(rate_limit.state.rate_limit_clients) == 2
