"""Deterministic storage-thread lifecycle checks; no live CLI or Android calls."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from artemis.context import ArtemisContext
from artemis.data_engine.engine import DataEngine
from artemis.data_engine.models import SessionMetadata


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(DataEngine, "_connect_ipc_locked", lambda self, **kwargs: False)
    # Keep the process-wide logging queue outside this controlled storage race.
    monkeypatch.setattr("artemis.data_engine.engine._CURRENT_DATA_ENGINE", None)
    ctx = SimpleNamespace(execution_setup=SimpleNamespace(traces_path=str(tmp_path)), device=None)
    engine = DataEngine(ctx)
    engine.current_session_id = uuid4()
    engine.storage.create_session(SessionMetadata(session_id=engine.current_session_id, initial_goal="thread lifecycle"))
    yield engine
    asyncio.run(engine.shutdown())


@pytest.mark.parametrize("observer", ["pending", "shutdown"])
def test_observer_cannot_miss_a_thread_paused_before_start(engine, monkeypatch, observer):
    """Force the append/start gap, then observe it before allowing start to finish."""
    start_entered = threading.Event()
    release_start = threading.Event()
    observation_entered = threading.Event()
    release_work = threading.Event()
    real_start = threading.Thread.start
    results = []
    errors = []

    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            if threading.current_thread().name not in ("submitter", "artemis-storage"):
                observation_entered.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    # This probe reports an attempted lock acquisition; it never changes locking.
    # On the original code the observer instead signals after its premature return.
    engine._pending_threads_lock = ObservedLock()

    def paused_start(thread):
        if thread.name == "artemis-storage":
            start_entered.set()
            assert release_start.wait(5)
        return real_start(thread)

    def store():
        assert release_work.wait(5)
        engine.update_session_device_info(saved=True)

    def observe():
        try:
            if observer == "pending":
                results.append(engine.has_pending_operations())
            else:
                asyncio.run(engine.shutdown())
                results.append(engine.storage.get_session(engine.current_session_id).device_info)
        except BaseException as exc:
            errors.append(exc)
        finally:
            observation_entered.set()

    monkeypatch.setattr(threading.Thread, "start", paused_start)
    submitter = threading.Thread(target=engine._run_in_background, args=(store,), name="submitter")
    reader = threading.Thread(target=observe, name="observer")
    try:
        submitter.start()
        assert start_entered.wait(5)
        reader.start()
        assert observation_entered.wait(5)
        release_start.set()
        submitter.join(5)
        assert not submitter.is_alive()
        if observer == "pending":
            reader.join(5)
        release_work.set()
        reader.join(5)
        assert not reader.is_alive()
        assert not errors
        assert results == ([True] if observer == "pending" else [{"saved": True}])
    finally:
        release_start.set()
        release_work.set()
        submitter.join(5)
        if reader.ident is not None:
            reader.join(5)


def test_fast_completion_leaves_no_thread(engine):
    for _ in range(100):
        engine._run_in_background(lambda: None)
    engine._wait_for_pending_threads()
    assert engine._pending_thread_snapshot() == []
    assert not engine.has_pending_operations()


def test_start_failure_is_propagated_and_unregistered(engine, monkeypatch):
    real_start = threading.Thread.start

    def fail_start(thread):
        if thread.name == "artemis-storage":
            raise RuntimeError("thread resource exhausted")
        return real_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="resource exhausted"):
        engine._run_in_background(lambda: None)
    assert engine._pending_thread_snapshot() == []
    assert not engine.has_pending_operations()


def test_storage_exception_is_logged_and_unregistered(engine, monkeypatch):
    error = Mock()
    monkeypatch.setattr("artemis.data_engine.engine.logger.error", error)

    def fail():
        raise ValueError("storage failed")

    engine._run_in_background(fail)
    engine._wait_for_pending_threads()
    assert engine._pending_thread_snapshot() == []
    assert "storage failed" in error.call_args.args[0]


def test_concurrent_submissions_remain_pending_until_completed(engine):
    count = 16
    entered = threading.Barrier(count + 1)
    release = threading.Event()
    completed = []

    def work(number):
        entered.wait(timeout=5)
        assert release.wait(5)
        completed.append(number)

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(engine._run_in_background, work, n) for n in range(count)]
            for future in futures:
                future.result(timeout=5)
        entered.wait(timeout=5)
        assert engine.has_pending_operations()
        assert len(engine._pending_thread_snapshot()) == count
    finally:
        release.set()
        engine._wait_for_pending_threads()
    assert sorted(completed) == list(range(count))
    assert not engine.has_pending_operations()


def test_shutdown_drains_followup_trace_scheduled_after_first_snapshot(engine, monkeypatch):
    parent_entered = threading.Event()
    snapshot_taken = threading.Event()
    child_entered = threading.Event()
    release_child = threading.Event()
    shutdown_finished = threading.Event()
    followup_wait = threading.Event()
    trace_ids = []
    step_id = uuid4()
    joined = []

    def persist_trace():
        child_entered.set()
        assert release_child.wait(5)
        trace_ids.append(engine.record_trace("tool", "followup", {"query": "persist"}, step_id=step_id))

    def parent():
        parent_entered.set()
        assert snapshot_taken.wait(5)
        engine._run_in_background(persist_trace)

    engine._run_in_background(parent)
    assert parent_entered.wait(5)
    original_join = threading.Thread.join

    def observe_join(thread, *args, **kwargs):
        if thread.name == "artemis-storage":
            joined.append(thread)
            if len(joined) == 1:
                snapshot_taken.set()
            else:
                followup_wait.set()
        return original_join(thread, *args, **kwargs)

    monkeypatch.setattr(threading.Thread, "join", observe_join)

    def stop():
        asyncio.run(engine.shutdown())
        shutdown_finished.set()
        followup_wait.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert child_entered.wait(5)
        assert followup_wait.wait(5)
        assert not shutdown_finished.is_set()
        release_child.set()
        stopper.join(5)
        assert shutdown_finished.is_set()
        traces = engine.storage.get_traces_for_step(step_id)
        assert len(trace_ids) == 1
        assert any(trace.trace_id == trace_ids[0] for trace in traces)
        assert not engine.has_pending_operations()
    finally:
        snapshot_taken.set()
        release_child.set()
        stopper.join(5)


@pytest.mark.asyncio
async def test_async_storage_task_path_is_preserved(engine):
    saved = []
    engine._run_in_background(saved.append, "async")
    assert engine._pending_tasks
    assert engine._pending_thread_snapshot() == []
    await engine.shutdown()
    assert saved == ["async"]
    assert not engine.has_pending_operations()
