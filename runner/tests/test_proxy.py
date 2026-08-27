"""Egress-proxy allowlist behavior, exercised against in-process listeners."""

import asyncio
from collections.abc import AsyncIterator

import httpx2 as httpx
import pytest

from egress_proxy import proxy


@pytest.fixture
async def upstream_server() -> AsyncIterator[str]:
    """A trivial plain-HTTP upstream we allowlist as 127.0.0.1."""

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readline()
        while (await reader.readline()) not in (b"\r\n", b"\n", b""):
            pass
        body = b'{"ok": true}'
        writer.write(
            b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\n"
            + f"content-length: {len(body)}\r\nconnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield f"http://127.0.0.1:{port}"


@pytest.fixture
async def proxy_server(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    monkeypatch.setenv("FLEET_EGRESS_ALLOWLIST", "127.0.0.1,allowed.example")
    server = await asyncio.start_server(proxy.handle_proxy_conn, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield f"http://127.0.0.1:{port}"


async def test_allowlisted_http_forwarding(proxy_server: str, upstream_server: str) -> None:
    async with httpx.AsyncClient(proxy=proxy_server) as client:
        resp = await client.get(f"{upstream_server}/anything")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


async def test_non_allowlisted_host_blocked(proxy_server: str) -> None:
    async with httpx.AsyncClient(proxy=proxy_server) as client:
        resp = await client.get("http://evil.example/exfil")
    assert resp.status_code == 403


async def test_non_allowlisted_connect_blocked(proxy_server: str) -> None:
    # CONNECT to a non-allowlisted host must be refused at the proxy.
    async with httpx.AsyncClient(proxy=proxy_server) as client:
        with pytest.raises(httpx.HTTPError):
            await client.get("https://evil.example/")


def test_allowlist_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLEET_EGRESS_ALLOWLIST", " A.example ,b.example,")
    assert proxy.allowed_hosts() == frozenset({"a.example", "b.example"})
    assert proxy.host_allowed("A.EXAMPLE")
    assert not proxy.host_allowed("c.example")
