"""Unit tests for ClamAV INSTREAM scanner (no daemon required — mocked socket)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.attachments.scanner import _MAX_SCAN, scan


@pytest.mark.asyncio
async def test_file_too_large_rejected() -> None:
    data = b"x" * (_MAX_SCAN + 1)
    is_clean, msg = await scan(data)
    assert not is_clean
    assert "too large" in msg


@pytest.mark.asyncio
async def test_scan_clean_file() -> None:
    reader = AsyncMock()
    reader.read = AsyncMock(return_value=b"stream: OK\n")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        is_clean, msg = await scan(b"safe content")

    assert is_clean
    assert msg.endswith("OK")


@pytest.mark.asyncio
async def test_scan_infected_file() -> None:
    reader = AsyncMock()
    reader.read = AsyncMock(return_value=b"stream: Eicar.test FOUND\n")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        is_clean, msg = await scan(b"eicar payload")

    assert not is_clean
    assert "FOUND" in msg


@pytest.mark.asyncio
async def test_scan_raises_on_connection_error() -> None:
    with patch("asyncio.open_connection", side_effect=OSError("Connection refused")):
        with pytest.raises(OSError):
            await scan(b"data")


@pytest.mark.asyncio
async def test_scan_multi_chunk_data() -> None:
    """Data larger than 8 KB is split into multiple chunks — result still correct."""
    reader = AsyncMock()
    reader.read = AsyncMock(return_value=b"stream: OK\n")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        is_clean, msg = await scan(b"A" * 20_000)

    assert is_clean


@pytest.mark.asyncio
async def test_scan_writer_always_closed_on_error() -> None:
    """writer.close() must be called even when reader.read raises."""
    reader = AsyncMock()
    reader.read = AsyncMock(side_effect=OSError("read error"))
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        with pytest.raises(OSError):
            await scan(b"data")

    writer.close.assert_called_once()
