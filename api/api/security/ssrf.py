"""SSRF-устойчив HTTP клиент за бъдещ харвест/жив proxy.

Когато порталът тегли данни от външни адреси (харвест на каталози, жив proxy към API на
титуляри), нападател може да подаде URL, който сочи към вътрешната мрежа или към облачния
metadata адрес (169.254.169.254). Този модул затваря повърхността за SSRF:

- **само HTTPS** (без ``file://``, ``http://``, ``gopher://`` и т.н.);
- **проверка на всички разрешени IP-та** — отхвърля loopback/private/link-local/multicast/
  reserved/unspecified адреси (вкл. IPv4-mapped IPv6);
- **пиниране на връзката към проверения IP** (анти-DNS-rebinding: TLS SNI/сертификатът остават
  по хоста, но сокетът се свързва към вече проверения адрес);
- **без пренасочвания** (redirect може да заобиколи проверката);
- **таймаут и таван на размера** (защита от бавни/огромни отговори).

По избор — allowlist на хостове (най-силната защита, когато наборът от източници е известен).

Режим C (docs/review-model.md): критичен компонент — подлежи на одит по сигурност.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Резолвер: хост → списък от IP низове. Инжектируем, за да е тестваемо без мрежа.
Resolver = Callable[[str], Sequence[str]]


class SsrfError(ValueError):
    """Целевият адрес е отхвърлен от политиката за безопасно теглене (fail-closed)."""


def _default_resolver(host: str) -> Sequence[str]:
    return sorted({str(info[4][0]) for info in socket.getaddrinfo(host, None)})


def is_blocked_address(ip: str) -> bool:
    """Истина, ако IP-то НЕ бива да се достига (вътрешно/специално предназначение)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # не можем да разберем адреса → отказваме
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) — проверяваме вложения IPv4.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local  # покрива 169.254.0.0/16 (облачен metadata) и fe80::/10
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


@dataclass(frozen=True)
class SafeFetchPolicy:
    """Правила за безопасно теглене. Сигурни стойности по подразбиране."""

    allowed_schemes: frozenset[str] = frozenset({"https"})
    host_allowlist: frozenset[str] | None = None  # None = без allowlist (само IP проверката)
    max_bytes: int = 8 * 1024 * 1024
    timeout_seconds: float = 10.0
    resolver: Resolver = field(default=_default_resolver, compare=False)


@dataclass(frozen=True)
class ValidatedTarget:
    host: str
    port: int
    path: str
    pinned_ip: str


def validate_target(url: str, policy: SafeFetchPolicy) -> ValidatedTarget:
    """Проверява URL спрямо политиката и връща проверена цел (или вдига :class:`SsrfError`)."""
    parts = urlsplit(url)
    if parts.scheme not in policy.allowed_schemes:
        raise SsrfError(f"схема {parts.scheme!r} не е разрешена")
    host = parts.hostname
    if not host:
        raise SsrfError("липсва хост в URL")
    if policy.host_allowlist is not None and host not in policy.host_allowlist:
        raise SsrfError(f"хост {host!r} не е в allowlist-а")

    ips = list(policy.resolver(host))
    if not ips:
        raise SsrfError(f"хостът {host!r} не се резолвира")
    for ip in ips:
        if is_blocked_address(ip):
            raise SsrfError(f"хостът {host!r} сочи към забранен адрес {ip}")

    port = parts.port or 443
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return ValidatedTarget(host=host, port=port, path=path, pinned_ip=ips[0])


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS връзка, свързана към предварително проверен IP (анти-DNS-rebinding)."""

    def __init__(
        self,
        host: str,
        port: int,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ):
        super().__init__(host, port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip
        self._ssl_context = context

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        # TLS SNI и проверката на сертификата остават по оригиналния хост, не по IP-то.
        self.sock = self._ssl_context.wrap_socket(sock, server_hostname=self.host)


@dataclass(frozen=True)
class FetchResponse:
    status: int
    headers: dict[str, str]
    body: bytes


def fetch(url: str, policy: SafeFetchPolicy | None = None) -> FetchResponse:
    """Безопасно GET теглене: без redirect, с таймаут и таван на размера.

    3xx се третира като грешка — пренасочванията не се следват, за да не заобиколят проверката.
    """
    cfg = policy or SafeFetchPolicy()
    target = validate_target(url, cfg)
    context = ssl.create_default_context()
    conn = _PinnedHTTPSConnection(
        target.host, target.port, target.pinned_ip, cfg.timeout_seconds, context
    )
    try:
        conn.request("GET", target.path, headers={"Host": target.host, "Accept": "*/*"})
        resp = conn.getresponse()
        if 300 <= resp.status < 400:
            raise SsrfError(f"пренасочване ({resp.status}) не се следва")
        body = resp.read(cfg.max_bytes + 1)
        if len(body) > cfg.max_bytes:
            raise SsrfError(f"отговорът надхвърля {cfg.max_bytes} байта")
        headers = {k.lower(): v for k, v in resp.getheaders()}
        return FetchResponse(status=resp.status, headers=headers, body=body)
    finally:
        conn.close()
