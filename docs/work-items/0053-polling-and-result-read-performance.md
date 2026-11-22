# Background polling and current-result performance

Benchmarked the demo after the [portfolio audit](0052-review-and-demo-polish.md).
The measurements compare the same operations against fresh synthetic profiles
on the pinned Compose stack. The existing recording shows the same workflow.

## Method

The baseline was commit `2c7e10e`. Both runs used macOS arm64, Docker Engine
29.9.3, Compose 5.7.0, PostgreSQL 18.6, and the pinned Python and Node images.
The workload populated the disposable profile through authenticated simulated
SMS, first with three inputs and then with sixteen. Chromium joined a real
LiveKit room and the harness made 24 sequential current-result requests at each
size, 65 ms apart after each response, after observing a current result. Scan
timings use successful scans with all discovered inputs prepared and no active
or newly started jobs in that scan. The background worker and browser continued
to run during the study.

Temporary instrumentation measured elapsed wall time around the executor scan
and result producer. SQL counts measure Python `psycopg.Connection.execute`
calls inside those operations. The HTTP timings include the local UI proxy and
the authenticated result endpoint. The sample sizes describe this local fixture.

## Joined-stack results

| Operation | Inputs | Samples before / after | Median before / after | p95 before / after | Python SQL calls before / after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Background scan | 3 | 27 / 23 | 152 / 123 ms | 206 / 193 ms | 69 / 23 |
| Background scan | 16 | 14 / 12 | 678 / 470 ms | 1,475 / 747 ms | 368 / 23 |
| Current-result HTTP read | 3 | 24 / 24 | 526 / 300 ms | 645 / 377 ms | 695 / 343 |
| Current-result HTTP read | 16 | 24 / 24 | 651 / 507 ms | 1,107 / 842 ms | 695 / 343 |

All 96 timed HTTP requests returned a current result. The SQL counts for those
rows come from the corresponding result producer runs and exclude SQL executed
by the Node gateway. Empty scans used zero Python SQL calls in both runs. The
baseline also logged one internal result capacity error and one failed scan
during the study. The optimized run recorded zero internal errors.

## Changes

- Read the discovered work IDs in one bounded, scoped PostgreSQL operation. The
  executor still rereads each prepared input in order, validates its original
  receipt and payload against the work, and admits jobs only after validation.
  The execution authority still checks eligibility before issuance.
  [Executor](../../services/channel_policy_demo/executor.py)
- Pass the checked execution view into each delivery inspection. Current reads
  still capture independent work, case, and delivery observations on both sides
  of the channel receipt read. Receipt binding, result bytes, revision, and the
  original deadline still govern publication.
  [Current-result producer](../../services/channel_policy_demo/current_result_producer.py)
- Read booking telemetry in one repeatable, read-only transaction. The snapshot
  still checks role, schema, and persisted limits. Lease acquisition and other
  state changes continue to take the admission lock.
  [Booking work queue](../../projects/agent-continuity/python/src/continuity_lab/postgres_work.py)

At sixteen booking rows, a separate 72-sample paired probe in the pinned Python
container measured booking telemetry at 20.24 ms median and 30.00 ms p95 before
the change, and 13.64 ms median and 20.59 ms p95 after it. With an admission lock
held for 75 ms, all 12 baseline reads waited. All 12 updated reads finished
before release. The result-feed invariant query measured 0.79 ms median and
0.94 ms p95 at sixteen events, so the feed query was left as implemented.

## Full demo verification

The final, uninstrumented image started on empty volumes. Chromium completed
text, recorded voice, End, simulated SMS, rejoin with a fresh policy result,
and the separate operator quote approval. The captured audio decoded with
three non-silent segments for the caller and agent. The ledger verifier found
three original inputs, three delivered policy results, and two closed rooms for
the same case. The operator flow produced one supplier effect and one receiver
receipt. `./demo verify` returned the same persisted identity digest before and
after a full `./demo down` and `./demo up`. The disposable verification stack
was reset afterward.

The retained Python suite passed 1,031 tests and 1,242 subtests. Five real
PostgreSQL baseline checks passed, including scoped batch reads and booking
metrics while admission was held. Ruff and strict mypy passed on the changed
runtime files.
