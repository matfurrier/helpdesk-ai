"""ClamAV INSTREAM scanner — raw asyncio socket, no pyclamd dependency."""

from __future__ import annotations

import asyncio
import struct

import structlog

from app.core.config import settings

log = structlog.get_logger()

_CHUNK = 8192
_MAX_SCAN = 25 * 1024 * 1024  # 25 MB hard cap


async def scan(data: bytes) -> tuple[bool, str]:
    """Scan *data* bytes via ClamAV INSTREAM protocol.

    Returns ``(is_clean, status_message)``.
    Raises ``OSError`` if the daemon is unreachable.
    """
    if len(data) > _MAX_SCAN:
        return False, "file too large for scanning"

    reader, writer = await asyncio.open_connection(settings.clamav_host, settings.clamav_port)
    try:
        writer.write(b"zINSTREAM\0")
        for i in range(0, len(data), _CHUNK):
            chunk = data[i : i + _CHUNK]
            writer.write(struct.pack(">I", len(chunk)) + chunk)
        writer.write(b"\x00\x00\x00\x00")
        await writer.drain()
        raw = await reader.read(1024)
    finally:
        writer.close()
        await writer.wait_closed()

    result = raw.decode(errors="replace").strip("\x00\n\r ")
    is_clean = result.endswith("OK")
    log.info("clamav.scan", result=result, is_clean=is_clean, size_bytes=len(data))
    return is_clean, result
