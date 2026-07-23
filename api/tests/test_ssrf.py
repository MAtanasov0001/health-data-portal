"""Тестове за SSRF-устойчивия клиент (режим C). Проверката е без мрежа (инжектиран резолвер)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from api.security.ssrf import (
    SafeFetchPolicy,
    SsrfError,
    is_blocked_address,
    validate_target,
)


def _resolver(*ips: str) -> object:
    def resolve(host: str) -> Sequence[str]:
        return list(ips)

    return resolve


# --- Класификация на адреси ----------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # private
        "192.168.1.1",  # private
        "172.16.0.1",  # private
        "169.254.169.254",  # облачен metadata (link-local)
        "0.0.0.0",  # unspecified
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "::ffff:10.0.0.1",  # IPv4-mapped private
        "not-an-ip",  # неразбираем → блокиран
    ],
)
def test_blocked_addresses(ip: str) -> None:
    assert is_blocked_address(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1::"])
def test_public_addresses_allowed(ip: str) -> None:
    assert is_blocked_address(ip) is False


# --- Проверка на цел -----------------------------------------------------------------


def test_https_public_host_ok() -> None:
    policy = SafeFetchPolicy(resolver=_resolver("93.184.216.34"))  # type: ignore[arg-type]
    target = validate_target("https://example.org/data.json?x=1", policy)
    assert target.host == "example.org"
    assert target.port == 443
    assert target.path == "/data.json?x=1"
    assert target.pinned_ip == "93.184.216.34"


def test_non_https_scheme_rejected() -> None:
    policy = SafeFetchPolicy(resolver=_resolver("93.184.216.34"))  # type: ignore[arg-type]
    for url in ("http://example.org/", "file:///etc/passwd", "gopher://example.org/"):
        with pytest.raises(SsrfError):
            validate_target(url, policy)


def test_internal_ip_rejected_before_connect() -> None:
    policy = SafeFetchPolicy(resolver=_resolver("169.254.169.254"))  # type: ignore[arg-type]
    with pytest.raises(SsrfError):
        validate_target("https://metadata.evil.example/latest", policy)


def test_any_resolved_internal_ip_rejects() -> None:
    # Дори един вътрешен адрес сред разрешените → отказ (защита от rebinding/множествени A).
    policy = SafeFetchPolicy(resolver=_resolver("93.184.216.34", "10.0.0.1"))  # type: ignore[arg-type]
    with pytest.raises(SsrfError):
        validate_target("https://example.org/", policy)


def test_host_allowlist_enforced() -> None:
    policy = SafeFetchPolicy(
        host_allowlist=frozenset({"trusted.example"}),
        resolver=_resolver("93.184.216.34"),  # type: ignore[arg-type]
    )
    assert validate_target("https://trusted.example/x", policy).host == "trusted.example"
    with pytest.raises(SsrfError):
        validate_target("https://other.example/x", policy)


def test_unresolvable_host_rejected() -> None:
    policy = SafeFetchPolicy(resolver=_resolver())  # type: ignore[arg-type]
    with pytest.raises(SsrfError):
        validate_target("https://ghost.example/", policy)
