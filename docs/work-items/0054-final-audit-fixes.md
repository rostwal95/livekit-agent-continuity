# Final audit fixes

## Changes

| Finding | Fix |
| --- | --- |
| LiveKit could create rooms outside the application’s lifecycle. | Disable automatic room creation in the demo. The application creates each room explicitly. |
| A failed or abandoned voice publication left the browser controls out of sync. | Enable voice turns after LiveKit confirms publication and the track is live. Retain ownership of late publication and cleanup before allowing a new source. |
| The acknowledgement timer could erase a known rejection. | Cancel the timer when a terminal receipt or rejection arrives. An uncertainty transition applies to pending input only. |
| Booking admission contention could stop the worker. | Retry on the next poll after a definite pre-claim lock timeout. Keep storage, lease, and post-claim failure handling. |
| An expired, result-less policy attempt could stay unresolved. | Bind new issuance to the exact expired predecessor under PostgreSQL admission. Keep the original request, deadline, and attempt budget. Only a newly issued attempt may call the specialist. |
| Room deletion could stay blocked after a rejection. | Reinspect the exact room before retrying a definitely rejected delete. A timed-out call remains uncertain and closure waits to observe the room absent. |
| The verifier counted the supplier and receiver rows independently of the booking. | Match the effect, completion event, payloads, and receiver identity to the same confirmed PostgreSQL booking. |
| The sharing copy’s Docker build could include local caches. | Carry the branch’s Docker exclusions into the sharing copy. |
| Three package-wide strict type checks failed, and a successful router retry used a deliberate 20 ms fault budget. | Type the CLI handler and supplier data boundaries. Give the successful retry a separate budget after testing abandonment. |

The joined behavior and the exact-count verifier are described in the
[architecture](../architecture.md) and [walkthrough](../demo.md).

## Verification

- The retained suites passed 1,037 Python tests, 1,244 Python subtests, and
  1,415 TypeScript tests. Strict mypy passed all 146 source files. Ruff and
  browser type checking passed.
- Six real PostgreSQL 18.6 checks passed. The recovery check exercised lease
  expiry, one new grant across concurrent requests, and refusal to deliver
  a late result from the superseded attempt. The booking admission test proved
  that a lock timeout reaches the worker as a distinct pre-claim error.
- A clean Docker build and Chromium walkthrough exercised text, recorded voice
  with audio playback, End, simulated SMS, rejoin with a fresh policy result,
  and exact operator approval. The verifier found three original inputs and
  three delivered results across two rooms, one supplier effect, and one
  receiver receipt. The complete result matched after restart, and the
  disposable containers and volumes were removed.
- The stricter verifier rejected a mismatched supplier effect and a mismatched
  completion receipt in separate copies of the synthetic ledgers.
