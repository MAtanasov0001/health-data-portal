"""Определяне на клиентския IP при наличие на доверени обратни проксита.

Ключово за коректно ограничаване на честотата и одита: ако вярваме сляпо на
``X-Forwarded-For``, клиент може да подправи хедъра и да заобиколи лимита или да
подведе одита. Затова вярваме само на толкова хопа отдясно, колкото са реално
конфигурираните проксита пред приложението (``trusted_proxy_hops``).
"""

from __future__ import annotations

from starlette.requests import Request


def client_ip(request: Request, trusted_proxy_hops: int) -> str:
    """Връща ефективния клиентски IP.

    При ``trusted_proxy_hops == 0`` се използва прекият сокет адрес (не се вярва на
    XFF). При N > 0 се взема N-тият адрес отдясно наляво в ``X-Forwarded-For`` — това е
    адресът, който доверените проксита не могат да са получили от клиента наготово.
    """
    peer = request.client.host if request.client else "unknown"
    if trusted_proxy_hops <= 0:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not chain:
        return peer
    index = trusted_proxy_hops
    if index > len(chain):
        # По-малко адреси от очакваното — вземи най-левия (най-близкия до клиента), но
        # това сочи погрешна конфигурация.
        return chain[0]
    return chain[-index]
