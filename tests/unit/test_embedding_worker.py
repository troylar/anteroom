"""Tests for the embedding worker."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anteroom.services.embedding_worker import EmbeddingWorker


class TestEmbeddingWorker:
    def _make_worker(self, db=None, service=None):
        db = db or MagicMock()
        service = service or AsyncMock()
        return EmbeddingWorker(db, service, batch_size=10)

    @pytest.mark.asyncio
    async def test_process_pending_embeds_messages(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        messages = [
            {"id": "m1", "conversation_id": "c1", "content": "Hello, this is a test message.", "role": "user"},
            {"id": "m2", "conversation_id": "c1", "content": "This is another test message.", "role": "assistant"},
        ]

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.get_unembedded_messages = MagicMock(return_value=messages)
            mock_storage.store_embedding = MagicMock()

            worker = self._make_worker(service=service)
            count = await worker.process_pending()

        assert count == 2
        assert mock_storage.store_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_process_pending_skips_short_messages(self) -> None:
        service = AsyncMock()

        messages = [
            {"id": "m1", "conversation_id": "c1", "content": "short", "role": "user"},
        ]

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.get_unembedded_messages = MagicMock(return_value=messages)

            worker = self._make_worker(service=service)
            count = await worker.process_pending()

        assert count == 0
        service.embed_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_pending_returns_zero_when_no_messages(self) -> None:
        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.get_unembedded_messages = MagicMock(return_value=[])

            worker = self._make_worker()
            count = await worker.process_pending()

        assert count == 0

    @pytest.mark.asyncio
    async def test_process_pending_handles_none_embeddings(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[None, [0.1, 0.2]])

        messages = [
            {"id": "m1", "conversation_id": "c1", "content": "First test message content", "role": "user"},
            {"id": "m2", "conversation_id": "c1", "content": "Second test message content", "role": "assistant"},
        ]

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.get_unembedded_messages = MagicMock(return_value=messages)
            mock_storage.store_embedding = MagicMock()

            worker = self._make_worker(service=service)
            count = await worker.process_pending()

        assert count == 1
        mock_storage.store_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_message_single(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.store_embedding = MagicMock()

            worker = self._make_worker(service=service)
            await worker.embed_message("m1", "This is a test message for embedding.", "c1")

        service.embed.assert_called_once_with("This is a test message for embedding.")
        mock_storage.store_embedding.assert_called_once()
        call_args = mock_storage.store_embedding.call_args
        # store_embedding is called with positional args: (db, message_id, conv_id, embedding, hash)
        assert call_args[0][1] == "m1"

    @pytest.mark.asyncio
    async def test_embed_message_skips_short(self) -> None:
        service = AsyncMock()

        with patch("anteroom.services.embedding_worker.storage"):
            worker = self._make_worker(service=service)
            await worker.embed_message("m1", "hi", "c1")

        service.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_message_handles_none_result(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=None)

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            worker = self._make_worker(service=service)
            await worker.embed_message("m1", "This is a test message for embedding.", "c1")

        mock_storage.store_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_message_uses_content_hash(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1])
        content = "This is a test message for content hash."
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.store_embedding = MagicMock()

            worker = self._make_worker(service=service)
            await worker.embed_message("m1", content, "c1")

        call_args = mock_storage.store_embedding.call_args
        # Check the content_hash positional or keyword arg
        all_args = list(call_args[0]) + list(call_args[1].values())
        assert expected_hash in all_args

    @pytest.mark.asyncio
    async def test_process_pending_continues_after_store_failure(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        messages = [
            {"id": "m1", "conversation_id": "c1", "content": "First test message content here", "role": "user"},
            {"id": "m2", "conversation_id": "c1", "content": "Second test message content here", "role": "assistant"},
        ]

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.get_unembedded_messages = MagicMock(return_value=messages)
            # First store_embedding raises, second succeeds
            mock_storage.store_embedding = MagicMock(side_effect=[Exception("DB error"), None])

            worker = self._make_worker(service=service)
            count = await worker.process_pending()

        # Should have counted only the successful one
        assert count == 1

    @pytest.mark.asyncio
    async def test_embed_message_handles_store_error(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1, 0.2])

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.store_embedding = MagicMock(side_effect=Exception("DB error"))

            worker = self._make_worker(service=service)
            # Should not raise
            await worker.embed_message("m1", "This is long enough to embed", "c1")

    @pytest.mark.asyncio
    async def test_run_forever_processes_and_stops(self) -> None:
        import asyncio

        service = AsyncMock()
        worker = self._make_worker(service=service)

        call_count = 0

        async def mock_process():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                worker.stop()
            return 0

        worker.process_pending = mock_process

        # run_forever with a tiny interval, should exit after stop()
        await asyncio.wait_for(worker.run_forever(interval=0.01), timeout=2.0)
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_content_hash_is_deterministic(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1])
        content = "This is a deterministic hash test."

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.store_embedding = MagicMock()

            worker = self._make_worker(service=service)
            await worker.embed_message("m1", content, "c1")
            await worker.embed_message("m2", content, "c2")

        # Both calls should use the same hash
        hash1 = mock_storage.store_embedding.call_args_list[0][0][4]
        hash2 = mock_storage.store_embedding.call_args_list[1][0][4]
        assert hash1 == hash2

    def test_stop_sets_flag(self) -> None:
        worker = self._make_worker()
        worker._running = True
        worker.stop()
        assert not worker._running

    @pytest.mark.asyncio
    async def test_embed_message_handles_transient_error(self) -> None:
        from anteroom.services.embeddings import EmbeddingTransientError

        service = AsyncMock()
        service.embed = AsyncMock(side_effect=EmbeddingTransientError("rate limited", status_code=429))

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            worker = self._make_worker(service=service)
            await worker.embed_message("m1", "This is a test message for embedding.", "c1")

        mock_storage.store_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_message_handles_permanent_error(self) -> None:
        from anteroom.services.embeddings import EmbeddingPermanentError

        service = AsyncMock()
        service.embed = AsyncMock(side_effect=EmbeddingPermanentError("model not found", status_code=404))

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            worker = self._make_worker(service=service)
            await worker.embed_message("m1", "This is a test message for embedding.", "c1")

        mock_storage.store_embedding.assert_not_called()


class TestEmbeddingWorkerBackoff:
    def _make_worker(self, db=None, service=None):
        db = db or MagicMock()
        service = service or AsyncMock()
        return EmbeddingWorker(db, service, batch_size=10)

    def test_initial_state(self) -> None:
        worker = self._make_worker()
        assert not worker.disabled
        assert worker.disabled_reason is None
        assert worker.consecutive_failures == 0
        assert worker.current_interval == 30.0

    def test_apply_backoff_increases_interval(self) -> None:
        worker = self._make_worker()
        worker._base_interval = 30.0
        worker._apply_backoff()
        assert worker.consecutive_failures == 1
        assert worker.current_interval == 60.0
        worker._apply_backoff()
        assert worker.consecutive_failures == 2
        assert worker.current_interval == 120.0

    def test_backoff_caps_at_max_interval(self) -> None:
        worker = self._make_worker()
        worker._base_interval = 30.0
        for _ in range(20):
            worker._apply_backoff()
        assert worker.current_interval == 300.0

    def test_reset_backoff_clears_state(self) -> None:
        worker = self._make_worker()
        worker._base_interval = 30.0
        worker._apply_backoff()
        worker._apply_backoff()
        assert worker.consecutive_failures == 2
        worker._reset_backoff()
        assert worker.consecutive_failures == 0
        assert worker.current_interval == 30.0

    def test_auto_disable_after_max_failures(self) -> None:
        from anteroom.services.embedding_worker import MAX_CONSECUTIVE_FAILURES

        worker = self._make_worker()
        worker._base_interval = 30.0
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            worker._apply_backoff()
        assert worker.disabled
        assert "Auto-disabled" in (worker.disabled_reason or "")

    def test_disable_permanent(self) -> None:
        worker = self._make_worker()
        worker._disable_permanent("model not found")
        assert worker.disabled
        assert worker.disabled_reason == "model not found"

    @pytest.mark.asyncio
    async def test_run_forever_backoff_on_transient_error(self) -> None:
        import asyncio

        from anteroom.services.embeddings import EmbeddingTransientError

        worker = self._make_worker()
        call_count = 0

        async def mock_process():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                worker.stop()
                return 0
            raise EmbeddingTransientError("rate limited", status_code=429)

        worker.process_pending = mock_process

        await asyncio.wait_for(worker.run_forever(interval=0.01), timeout=5.0)
        assert call_count >= 3
        assert worker.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_run_forever_disables_on_permanent_error(self) -> None:
        import asyncio

        from anteroom.services.embeddings import EmbeddingPermanentError

        worker = self._make_worker()

        async def mock_process():
            raise EmbeddingPermanentError("model not found", status_code=404)

        worker.process_pending = mock_process

        # run_forever should disable and keep looping (sleeping); we stop it
        async def stop_after_delay():
            await asyncio.sleep(0.05)
            worker.stop()

        asyncio.create_task(stop_after_delay())
        await asyncio.wait_for(worker.run_forever(interval=0.01), timeout=2.0)
        assert worker.disabled
        assert "Permanent" in (worker.disabled_reason or "")

    @pytest.mark.asyncio
    async def test_run_forever_resets_backoff_on_success(self) -> None:
        import asyncio

        from anteroom.services.embeddings import EmbeddingTransientError

        worker = self._make_worker()
        call_count = 0

        async def mock_process():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise EmbeddingTransientError("rate limited", status_code=429)
            if call_count == 2:
                return 1  # success
            worker.stop()
            return 0

        worker.process_pending = mock_process

        await asyncio.wait_for(worker.run_forever(interval=0.01), timeout=5.0)
        assert worker.consecutive_failures == 0
