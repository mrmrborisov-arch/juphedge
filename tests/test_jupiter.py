"""Smoke tests that don't depend on live APIs — validate pure-function code paths."""
from __future__ import annotations

from src import jupiter


def test_correlation_proxy_table_has_sol_to_btc() -> None:
    assert jupiter._CRYPTO_CORRELATION_PROXY["SOL"] == "BTC"
    assert jupiter._CRYPTO_CORRELATION_PROXY["JUP"] == "BTC"


def test_rpc_scan_too_big_is_runtime_error() -> None:
    assert issubclass(jupiter.RPCScanTooBigError, RuntimeError)


def test_stables_registry_has_usdc_and_usdt() -> None:
    from src.analyzer import STABLES

    # USDC mint
    assert "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" in STABLES
    # USDT mint
    assert "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB" in STABLES
