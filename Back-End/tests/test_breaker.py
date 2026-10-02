"""B.4 — circuit breaker do provider de LLM."""
import time

from edubot.agent import llm


def setup_function(_):
    llm.reset_breaker()


def teardown_function(_):
    llm.reset_breaker()


def test_breaker_opens_after_threshold(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    assert llm.is_real() is True
    for _ in range(llm.BREAKER_THRESHOLD):
        llm._record_failure()
    assert llm.circuit_open() is True
    # com o breaker aberto, is_real() degrada para False (usa template/mock)
    assert llm.is_real() is False


def test_success_resets_counter(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    llm._record_failure()
    llm._record_failure()
    llm._record_success()  # zera antes de abrir
    llm._record_failure()
    assert llm.circuit_open() is False
    assert llm.is_real() is True


def test_cooldown_expires(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    for _ in range(llm.BREAKER_THRESHOLD):
        llm._record_failure()
    assert llm.circuit_open() is True
    # força a janela de esfriamento para o passado
    monkeypatch.setattr(llm, "_circuit_open_until", time.time() - 1)
    assert llm.circuit_open() is False
    assert llm.is_real() is True
