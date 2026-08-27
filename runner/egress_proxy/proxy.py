"""OffsideFleet egress service (M1.S3, ADR-002).

Two listeners in one process:

1. Forward proxy (:8888) — the ONLY route out of the internal agent network.
   Supports CONNECT (https) and absolute-form plain-HTTP forwarding, both
   gated by a host allowlist. Everything else is refused.

2. Model reverse-proxy (:8889) — forwards Messages API requests to
   https://api.anthropic.com, injecting the platform API key HERE so agent
   containers never hold it (no ambient credentials). Reachable only from the
   internal network; per-run auth hardening lands with the tool broker (M4).
"""

import asyncio
import contextlib
import logging
import os
from urllib.parse import urlsplit

import httpx2 as httpx

logger = logging.getLogger("egress-proxy")

PROXY_PORT = int(os.environ.get("FLEET_PROXY_PORT", "8888"))
MODEL_PROXY_PORT = int(os.environ.get("FLEET_MODEL_PROXY_PORT", "8889"))
ANTHROPIC_BASE = os.environ.get("FLEET_MODEL_UPSTREAM", "https://api.anthropic.com")


def allowed_hosts() -> frozenset[str]:
    raw = os.environ.get(
        "FLEET_EGRESS_ALLOWLIST", "api.anthropic.com,host.docker.internal"
    )
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


def host_allowed(host: str) -> bool:
    return host.lower() in allowed_hosts()


# --------------------------------------------------------------------------
# Forward proxy (CONNECT + absolute-form HTTP)
# --------------------------------------------------------------------------


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def _refuse(writer: asyncio.StreamWriter, status: str) -> None:
    writer.write(f"HTTP/1.1 {status}\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    writer.close()


async def handle_proxy_conn(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=10)
    except TimeoutError:
        writer.close()
        return
    if not request_line:
        writer.close()
        return

    try:
        method, target, _version = request_line.decode("latin1").split(" ", 2)
    except ValueError:
        await _refuse(writer, "400 Bad Request")
        return

    # Drain request headers (kept for the plain-HTTP branch).
    headers: list[bytes] = []
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        headers.append(line)

    if method.upper() == "CONNECT":
        host, _, port_s = target.partition(":")
        port = int(port_s or "443")
        if not host_allowed(host):
            logger.warning("BLOCKED CONNECT %s:%s", host, port)
            await _refuse(writer, "403 Forbidden")
            return
        try:
            up_reader, up_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10
            )
        except (OSError, TimeoutError):
            await _refuse(writer, "502 Bad Gateway")
            return
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        logger.info("CONNECT %s:%s allowed", host, port)
        await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))
        return

    # Absolute-form plain HTTP (e.g. GET http://host.docker.internal:8000/...)
    split = urlsplit(target)
    if not split.hostname:
        await _refuse(writer, "400 Bad Request")
        return
    if not host_allowed(split.hostname):
        logger.warning("BLOCKED %s %s", method, split.hostname)
        await _refuse(writer, "403 Forbidden")
        return
    port = split.port or 80
    try:
        up_reader, up_writer = await asyncio.wait_for(
            asyncio.open_connection(split.hostname, port), timeout=10
        )
    except (OSError, TimeoutError):
        await _refuse(writer, "502 Bad Gateway")
        return
    path = split.path or "/"
    if split.query:
        path += f"?{split.query}"
    up_writer.write(f"{method} {path} HTTP/1.1\r\n".encode("latin1"))
    for h in headers:
        if not h.lower().startswith((b"proxy-connection:", b"connection:")):
            up_writer.write(h)
    up_writer.write(b"Connection: close\r\n\r\n")
    await up_writer.drain()
    logger.info("%s %s allowed", method, split.hostname)
    await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))


# --------------------------------------------------------------------------
# Model reverse-proxy (key injection)
# --------------------------------------------------------------------------

_HOP_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "x-api-key",
    "authorization",
}


async def handle_model_conn(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=30)
        if not request_line:
            writer.close()
            return
        method, path, _version = request_line.decode("latin1").split(" ", 2)

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            name, _, value = line.decode("latin1").partition(":")
            headers[name.strip().lower()] = value.strip()

        body = b""
        if "content-length" in headers:
            body = await reader.readexactly(int(headers["content-length"]))

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            await _refuse(writer, "503 Service Unavailable")
            return

        fwd_headers = {k: v for k, v in headers.items() if k not in _HOP_HEADERS}
        fwd_headers["x-api-key"] = api_key  # injected here; never in the container

        async with httpx.AsyncClient(base_url=ANTHROPIC_BASE, timeout=600) as client:
            upstream = await client.request(method, path, headers=fwd_headers, content=body)

        writer.write(f"HTTP/1.1 {upstream.status_code} OK\r\n".encode("latin1"))
        for name, value in upstream.headers.items():
            if name.lower() not in ("transfer-encoding", "connection", "content-length"):
                writer.write(f"{name}: {value}\r\n".encode("latin1"))
        writer.write(f"content-length: {len(upstream.content)}\r\n".encode("latin1"))
        writer.write(b"connection: close\r\n\r\n")
        writer.write(upstream.content)
        await writer.drain()
    except Exception:
        logger.exception("model proxy error")
        try:
            await _refuse(writer, "502 Bad Gateway")
            return
        except Exception:
            pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    proxy = await asyncio.start_server(handle_proxy_conn, "0.0.0.0", PROXY_PORT)
    model = await asyncio.start_server(handle_model_conn, "0.0.0.0", MODEL_PROXY_PORT)
    logger.info(
        "egress proxy on :%s, model proxy on :%s, allowlist=%s",
        PROXY_PORT,
        MODEL_PROXY_PORT,
        sorted(allowed_hosts()),
    )
    async with proxy, model:
        await asyncio.gather(proxy.serve_forever(), model.serve_forever())


if __name__ == "__main__":
    asyncio.run(main())
