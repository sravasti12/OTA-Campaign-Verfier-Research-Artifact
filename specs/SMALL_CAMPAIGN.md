# Small campaign model: definitions

This is the first formal model in the repo. The definitions here were written before the model. The TLA+ is in
[tla/OTACampaign.tla](tla/OTACampaign.tla). Results and trace explanations are in
[../docs/SMALL_CAMPAIGN_RESULTS.md](../docs/SMALL_CAMPAIGN_RESULTS.md).

## The campaign

Three ECUs move from version 1 to version 2, taken from `examples/parallel_campaign.json`:

- **gateway**
- **brake**, with one dependency: **brake v2 requires gateway v2** (`brake-needs-gateway`)
- **infotainment**, with no dependencies

Each ECU has two slots. It runs from one while the new image is written to the other.

## The correct design

1. Each ECU downloads the image to its inactive slot and verifies it.
2. Each ECU activates version 2 (a trial). Brake may activate only after gateway has.
3. Each ECU passes a health check.
4. When all three are healthy, the campaign commits.
5. On any failure the campaign stops and rolls back **every** ECU on version 2, undoing dependents first (brake before gateway).
   It then ends as aborted.

## Faults

Each fault uses one unit of a budget `MaxFaults`, checked at 0, 1 and 2.

| Fault | Effect |
| --- | --- |
| Download failure | The ECU has no image; the campaign rolls back |
| Corrupt download | The image arrives damaged; verification should reject it |
| Trial failure | A running version 2 image fails its health check; the campaign rolls back |
| Vehicle-wide power loss | Unverified downloads are lost; the campaign rolls back. It can also strike during rollback, which then resumes |

## Properties

### Safety: nothing bad ever happens

**S1. Compatible at all times.** In every state the vehicle can reach, if brake runs version 2 then gateway runs version 2.

**S2. A way back is kept.** Until the campaign commits, every ECU running version 2 still holds its old version 1 image.

**S3. All or nothing.** Once the campaign has ended, all ECUs run version 2 or all run version 1. No mix.

**S4. Only verified images run.** No ECU ever runs a corrupt image.

### Liveness: something good eventually happens

**L1. The campaign always finishes.** Every execution eventually reaches committed or aborted, assuming the steps that can
run do eventually run, and faults are bounded by `MaxFaults`.

## Flawed variants

The same model is used throughout. The constant `Flaw` changes one design decision.

| Variant | Design mistake |
| --- | --- |
| `LocalRollback` | Only the ECU that reported the failure rolls back, without regard to dependents. This is the "roll back A without B" case |
| `EarlyErase` | Each ECU erases its old image as soon as it activates, to free flash |
| `SkipVerify` | Verification always passes. Added so that S4 is shown to be able to fail |

## Expected verdicts, recorded before running

| Design | S1 | S2 | S3 | S4 | L1 |
| --- | --- | --- | --- | --- | --- |
| Correct | holds | holds | holds | holds | holds |
| `LocalRollback` | violated | holds | violated | holds | holds |
| `EarlyErase` | holds | violated | holds | holds | violated |
| `SkipVerify` | holds | holds | holds | violated | holds |

## What this model leaves out

This is a design-level model of one small campaign, not evidence about real vehicles.

- Download, verification, activation and each rollback switch are single atomic steps. Torn writes and half-done switches are not modelled.
- A rollback switch cannot itself fail, apart from being delayed by power loss.
- The coordinator's campaign state is assumed durable, so it survives power loss.
- There is no timing and no timeout event, and no retries. The timeout fault in `PLAN.md` is not in this model yet.
- There is no message loss between coordinator and ECUs.
- Results are bounded to at most 2 faults.
