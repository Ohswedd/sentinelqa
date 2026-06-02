# Distributed run shards

`engine.runner.sharding` already lets one host split a run into `N`
independent slices ("shard 1 of 4", "shard 2 of 4", ...). The
distributed extension lets those slices land on **different machines**
that coordinate through a shared queue.

The engine ships the wire contract (Protocols + payloads) and an
in-memory reference implementation. Wiring it to a real queue (Redis,
Postgres `LISTEN/NOTIFY`, SQS, ...) is intentionally out of tree — the
queue choice is operational, not engine concern.

## Contract

`engine/runner/shards/protocol.py` defines four dataclasses and two
Protocols.

### Payloads

```python
ShardTask(task_id, run_id, shard_index, shard_total, spec_paths, payload)
ShardLease(task, worker_id, leased_at, expires_at)
ShardResult(task_id, run_id, worker_id, status,
            findings_json, module_results_json, error_message)
```

`findings_json` and `module_results_json` are serialised JSON strings,
not parsed objects, so the queue can ship results across machines
without depending on the engine domain model. The consumer
deserialises against `schema_version`.

### Protocols

```python
class ShardCoordinator(Protocol):
    def enqueue(task: ShardTask) -> None: ...
    def claim(worker_id, lease_seconds=60) -> ShardLease | None: ...
    def heartbeat(worker_id, task_id) -> bool: ...
    def complete(result: ShardResult) -> None: ...
    def fail(task_id, *, worker_id, error_message) -> None: ...
    def results(run_id) -> tuple[ShardResult, ...]: ...
    def pending(run_id) -> int: ...

class ShardWorker(Protocol):
    worker_id: str
    def execute(lease: ShardLease) -> ShardResult: ...
```

### Invariants

1. **Exclusive claim.** A coordinator that hands the same task to two
   workers violates the contract. Backends without atomic claim (e.g.
   naive Redis LIST + LPOP races) must add a lease lock.
2. **Reclaim on lease expiry.** A worker that crashes mid-task drops
   its lease silently; the coordinator must move the task back to
   `pending` and let another worker claim it.
3. **Stateless workers.** A worker that restarts in the middle of a
   run must be safe to re-claim work. Workers persist nothing locally
   except the artefacts they're producing.
4. **Result idempotence.** A worker may complete the same task more
   than once (network retry, etc.); the coordinator should accept the
   first and reject duplicates from another worker.

## Reference implementation

`engine/runner/shards/in_memory.py` ships an `InMemoryCoordinator`
that holds state in a process-local dict guarded by a `threading.RLock`.
Use it for:

- unit-testing a worker against the Protocol without a real queue,
- single-host runs that still want to exercise the wire format end-to-end,
- a conformance target for new queue backends: run the same test
  suite (`tests/unit/runner/shards/test_in_memory.py`) against your
  backend; behaviour must match.

## Writing a queue backend

A Redis backend (sketch — engine ships no Redis dep):

```python
class RedisCoordinator:
    def __init__(self, redis_client, queue_key):
        self._r = redis_client
        self._key = queue_key

    def enqueue(self, task: ShardTask) -> None:
        self._r.xadd(self._key, {"task": json.dumps(asdict(task))})

    def claim(self, worker_id: str, *, lease_seconds: int = 60):
        # XREADGROUP + XCLAIM gives exclusive claim semantics.
        ...
```

The full implementation must:

- Provide `claim` semantics equivalent to Redis Streams' `XREADGROUP` +
  pending-entry-list, or Postgres' `SELECT ... FOR UPDATE SKIP LOCKED`.
- Track lease expiry so a dead worker's task is reclaimed (Redis
  Streams: PEL idle time; Postgres: `expires_at` column + a sweeper).
- Persist results in a separate keyspace so a queue purge doesn't drop
  completed work.

The conformance test suite (`tests/unit/runner/shards/test_in_memory.py`)
should pass verbatim against the new backend — parameterise the
fixture so the same test file exercises both.

## Not yet implemented

The Protocol ships in v1.8.0; wiring the _Local_ runner to drive a
shard worker is a follow-up. Until then, the seam exists for:

- Operators to write their own coordinator + workers and orchestrate
  out-of-band.
- Plugin authors to ship a `RunnerPlugin` (per
  `packages/python-sdk/src/sentinelqa/plugins.py:RunnerPlugin`) that
  speaks the shard Protocol on the wire.

When the engine itself starts spawning shard workers, this doc gets a
"Built-in orchestration" section above this one.
