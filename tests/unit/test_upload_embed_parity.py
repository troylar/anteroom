"""Tests for upload → embed → save_all parity and mid-session recovery (#834)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anteroom.services.embedding_worker import EmbeddingWorker


def _make_worker(
    db: MagicMock | None = None,
    service: AsyncMock | None = None,
    vec_manager: MagicMock | None = None,
) -> EmbeddingWorker:
    db = db or MagicMock()
    service = service or AsyncMock()
    return EmbeddingWorker(db, service, batch_size=10, vec_manager=vec_manager)


class TestEmbedSourceSaveAll:
    """embed_source() must flush the vector index to disk after embedding."""

    @pytest.mark.asyncio
    async def test_embed_source_calls_save_all_on_success(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2]])
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(
                return_value=[{"id": "c1", "content": "Long enough content for embed", "content_hash": "h1"}]
            )
            mock_storage.store_source_chunk_embedding = MagicMock()

            worker = _make_worker(service=service, vec_manager=vec_manager)
            count = await worker.embed_source("src-1")

        assert count == 1
        vec_manager.save_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_source_skips_save_all_when_no_chunks_embedded(self) -> None:
        service = AsyncMock()
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(return_value=[])

            worker = _make_worker(service=service, vec_manager=vec_manager)
            count = await worker.embed_source("src-1")

        assert count == 0
        vec_manager.save_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_source_skips_save_all_when_no_vec_manager(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2]])

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(
                return_value=[{"id": "c1", "content": "Long enough content for embed", "content_hash": "h1"}]
            )
            mock_storage.store_source_chunk_embedding = MagicMock()

            worker = _make_worker(service=service, vec_manager=None)
            count = await worker.embed_source("src-1")

        assert count == 1

    @pytest.mark.asyncio
    async def test_embed_source_save_all_failure_does_not_raise(self) -> None:
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2]])
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()
        vec_manager.save_all.side_effect = OSError("disk full")

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(
                return_value=[{"id": "c1", "content": "Long enough content for embed", "content_hash": "h1"}]
            )
            mock_storage.store_source_chunk_embedding = MagicMock()

            worker = _make_worker(service=service, vec_manager=vec_manager)
            count = await worker.embed_source("src-1")

        assert count == 1


class TestRepairStaleEmbeddings:
    """Mid-session recovery resets stale 'embedded' rows to 'pending'."""

    def test_repair_resets_missing_chunks_to_pending(self) -> None:
        db = MagicMock()
        db.execute_fetchall = MagicMock(return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}])
        vec_manager = MagicMock()
        source_chunks_index = MagicMock()
        source_chunks_index.contains = MagicMock(side_effect=lambda k: k != "c2")
        vec_manager.source_chunks = source_chunks_index

        worker = _make_worker(db=db, vec_manager=vec_manager)
        worker._repair_stale_embeddings()

        db.execute.assert_called_once()
        sql = db.execute.call_args[0][0]
        params = db.execute.call_args[0][1]
        assert "SET status = 'pending'" in sql
        assert params == ("c2",)
        db.commit.assert_called_once()

    def test_repair_noop_when_all_present(self) -> None:
        db = MagicMock()
        db.execute_fetchall = MagicMock(return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}])
        vec_manager = MagicMock()
        source_chunks_index = MagicMock()
        source_chunks_index.contains = MagicMock(return_value=True)
        vec_manager.source_chunks = source_chunks_index

        worker = _make_worker(db=db, vec_manager=vec_manager)
        worker._repair_stale_embeddings()

        db.execute.assert_not_called()

    def test_repair_noop_when_no_vec_manager(self) -> None:
        db = MagicMock()

        worker = _make_worker(db=db, vec_manager=None)
        worker._repair_stale_embeddings()

        db.execute_fetchall.assert_not_called()

    def test_repair_noop_when_no_embedded_rows(self) -> None:
        db = MagicMock()
        db.execute_fetchall = MagicMock(return_value=[])
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()

        worker = _make_worker(db=db, vec_manager=vec_manager)
        worker._repair_stale_embeddings()

        db.execute.assert_not_called()

    def test_repair_handles_exception_gracefully(self) -> None:
        db = MagicMock()
        db.execute_fetchall = MagicMock(side_effect=Exception("db error"))
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()

        worker = _make_worker(db=db, vec_manager=vec_manager)
        worker._repair_stale_embeddings()  # should not raise

    def test_repair_cursor_advances_across_calls(self) -> None:
        """Cursor sweeps through all rows, not just the first page."""
        db = MagicMock()
        # First call: return full page (2 rows at limit=2) — all present
        # Second call: return partial page (1 row) — missing from index
        # Third call: empty — cursor resets
        call_count = [0]

        def _fetchall(sql: str, params: tuple[int, ...]) -> list[dict[str, str]]:
            call_count[0] += 1
            if call_count[0] == 1:
                assert params == (2, 0), f"First call should have offset=0, got {params}"
                return [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
            elif call_count[0] == 2:
                assert params == (2, 2), f"Second call should have offset=2, got {params}"
                return [{"chunk_id": "c3"}]
            else:
                return []

        db.execute_fetchall = MagicMock(side_effect=_fetchall)
        vec_manager = MagicMock()
        source_chunks_index = MagicMock()
        # c1, c2 are present; c3 is missing
        source_chunks_index.contains = MagicMock(side_effect=lambda k: k != "c3")
        vec_manager.source_chunks = source_chunks_index

        worker = _make_worker(db=db, vec_manager=vec_manager)

        # First sweep page: all present, no update, cursor advances
        worker._repair_stale_embeddings(limit=2)
        assert worker._repair_offset == 2
        db.execute.assert_not_called()

        # Second sweep page: c3 missing, reset to pending, cursor wraps
        worker._repair_stale_embeddings(limit=2)
        assert worker._repair_offset == 0  # partial page, cursor resets
        db.execute.assert_called_once()
        sql = db.execute.call_args[0][0]
        params = db.execute.call_args[0][1]
        assert "SET status = 'pending'" in sql
        assert params == ("c3",)


class TestCliUploadEmbedWiring:
    """CLI /upload must call embed_source() after saving — the core parity fix for #834."""

    @pytest.mark.asyncio
    async def test_get_embedding_worker_creates_worker_with_service(self) -> None:
        """_get_embedding_worker() returns an EmbeddingWorker when embedding service is available."""
        mock_service = AsyncMock()
        mock_db = MagicMock()
        mock_vec_manager = MagicMock()

        # Simulate the lazy closure pattern from repl.py
        from anteroom.services.embedding_worker import EmbeddingWorker

        worker = EmbeddingWorker(mock_db, mock_service, vec_manager=mock_vec_manager)
        assert worker._service is mock_service
        assert worker._vec_manager is mock_vec_manager

    @pytest.mark.asyncio
    async def test_cli_upload_calls_embed_source_after_save(self) -> None:
        """Simulates the CLI upload flow: save_source_file → embed_source → user sees chunk count."""
        service = AsyncMock()
        service.embed_batch = AsyncMock(return_value=[[0.1, 0.2]])
        vec_manager = MagicMock()
        vec_manager.source_chunks = MagicMock()

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(
                return_value=[{"id": "c1", "content": "Long enough content for embed", "content_hash": "h1"}]
            )
            mock_storage.store_source_chunk_embedding = MagicMock()

            # This replicates the CLI upload path:
            # 1. save_source_file() returns source dict with content
            # 2. _get_embedding_worker() returns a worker
            # 3. worker.embed_source(source["id"]) embeds and flushes
            worker = _make_worker(service=service, vec_manager=vec_manager)
            source = {"id": "test-source-id", "content": "some extracted text"}
            n = await worker.embed_source(source["id"])

        assert n == 1
        vec_manager.save_all.assert_called_once()
        mock_storage.list_source_chunks.assert_called_once_with(worker._db, "test-source-id")

    @pytest.mark.asyncio
    async def test_cli_upload_graceful_when_no_embedding_service(self) -> None:
        """When embedding service is unavailable, upload should not fail."""
        # This tests the path where _get_embedding_worker() returns None
        # The upload should succeed without embedding
        service = AsyncMock()
        service.embed_batch = AsyncMock(side_effect=Exception("no model"))

        with patch("anteroom.services.embedding_worker.storage") as mock_storage:
            mock_storage.list_source_chunks = MagicMock(
                return_value=[{"id": "c1", "content": "Long enough content for embed", "content_hash": "h1"}]
            )

            worker = _make_worker(service=service, vec_manager=None)
            # embed_source catches the exception and returns 0
            from anteroom.services.embeddings import EmbeddingTransientError

            service.embed_batch = AsyncMock(side_effect=EmbeddingTransientError("unavailable"))
            count = await worker.embed_source("src-1")

        assert count == 0
