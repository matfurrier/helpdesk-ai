"""Unit tests for MinIO storage helpers (Minio client mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.attachments.storage import ensure_bucket, presigned_url, put


@pytest.mark.asyncio
async def test_put_returns_correct_key_prefix() -> None:
    mc = MagicMock()
    with patch("app.services.attachments.storage._client", return_value=mc):
        key = await put(b"data", "ticket-abc", "report.pdf", "application/pdf")

    assert key.startswith("tickets/ticket-abc/")
    assert key.endswith("report.pdf")
    mc.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_put_sanitizes_special_chars_in_filename() -> None:
    mc = MagicMock()
    with patch("app.services.attachments.storage._client", return_value=mc):
        key = await put(b"data", "t1", "my file (1).pdf", "application/pdf")

    # spaces and parentheses become underscores
    assert "my_file__1_.pdf" in key


@pytest.mark.asyncio
async def test_put_truncates_filename_to_100_chars() -> None:
    mc = MagicMock()
    long_name = "a" * 150 + ".pdf"
    with patch("app.services.attachments.storage._client", return_value=mc):
        key = await put(b"data", "t1", long_name, "application/pdf")

    filename_part = key.split("/")[-1]
    assert len(filename_part) <= 100


@pytest.mark.asyncio
async def test_presigned_url_delegates_to_client() -> None:
    mc = MagicMock()
    mc.presigned_get_object = MagicMock(return_value="https://minio/bucket/key?sig=abc")

    with patch("app.services.attachments.storage._client", return_value=mc):
        url = await presigned_url("tickets/t1/abc/file.pdf")

    assert url == "https://minio/bucket/key?sig=abc"
    mc.presigned_get_object.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_bucket_creates_when_missing() -> None:
    mc = MagicMock()
    mc.bucket_exists = MagicMock(return_value=False)
    mc.make_bucket = MagicMock()

    with patch("app.services.attachments.storage._client", return_value=mc):
        await ensure_bucket()

    mc.make_bucket.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_bucket_skips_when_already_exists() -> None:
    mc = MagicMock()
    mc.bucket_exists = MagicMock(return_value=True)
    mc.make_bucket = MagicMock()

    with patch("app.services.attachments.storage._client", return_value=mc):
        await ensure_bucket()

    mc.make_bucket.assert_not_called()
