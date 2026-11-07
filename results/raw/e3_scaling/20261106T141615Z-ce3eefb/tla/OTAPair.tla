---- MODULE OTAPair ----
\* Abstraction of OTACampaign to two ECUs plus "the rest of the vehicle".
\* Soundness argument: docs/PAIR_ABSTRACTION_SOUNDNESS.md
\*
\* Differences from OTACampaign:
\*   1. Only the two ECUs in ECUs are modelled.
\*   2. EnvFail: any other ECU may fail at any time, starting a rollback.
\*   3. There is no fault budget: faults may happen any number of times.
\* Commit and FinishRollback look only at these two ECUs, which allows more
\* behaviour than the real guards do. No liveness result carries over.
EXTENDS Naturals

CONSTANTS
    ECUs,       \* exactly two ECUs
    Deps,       \* dependencies between those two
    Flaw,       \* same meaning as in OTACampaign
    EnvEnabled  \* TRUE. FALSE only as a negative control for the refinement check

VARIABLES active, inactive, stage, corrupt, campaign, culprit

vars == <<active, inactive, stage, corrupt, campaign, culprit>>

Ended == {"committed", "aborted"}

Init ==
    /\ active = [e \in ECUs |-> 1]
    /\ inactive = [e \in ECUs |-> 0]
    /\ stage = [e \in ECUs |-> "idle"]
    /\ corrupt = [e \in ECUs |-> FALSE]
    /\ campaign = "run"
    /\ culprit = {}

Download(e) ==
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "downloaded"]
    /\ UNCHANGED <<active, inactive, corrupt, campaign, culprit>>

Verify(e) ==
    /\ campaign = "run" /\ stage[e] = "downloaded"
    /\ ~corrupt[e] \/ Flaw = "SkipVerify"
    /\ stage' = [stage EXCEPT ![e] = "verified"]
    /\ inactive' = [inactive EXCEPT ![e] = 2]
    /\ UNCHANGED <<active, corrupt, campaign, culprit>>

VerifyReject(e) ==
    /\ campaign = "run" /\ stage[e] = "downloaded"
    /\ corrupt[e] /\ Flaw /= "SkipVerify"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ UNCHANGED <<active, inactive, corrupt>>

Activate(e) ==
    /\ campaign = "run" /\ stage[e] = "verified"
    /\ \A dep \in Deps : dep[1] = e => active[dep[2]] = 2
    /\ active' = [active EXCEPT ![e] = 2]
    /\ inactive' = [inactive EXCEPT ![e] = IF Flaw = "EarlyErase" THEN 0 ELSE 1]
    /\ stage' = [stage EXCEPT ![e] = "trial"]
    /\ UNCHANGED <<corrupt, campaign, culprit>>

Confirm(e) ==
    /\ campaign = "run" /\ stage[e] = "trial"
    /\ stage' = [stage EXCEPT ![e] = "healthy"]
    /\ UNCHANGED <<active, inactive, corrupt, campaign, culprit>>

Commit ==
    /\ campaign = "run"
    /\ \A e \in ECUs : stage[e] = "healthy"
    /\ campaign' = "committed"
    /\ UNCHANGED <<active, inactive, stage, corrupt, culprit>>

DownloadFail(e) ==
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ UNCHANGED <<active, inactive, corrupt>>

DownloadCorrupt(e) ==
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "downloaded"]
    /\ corrupt' = [corrupt EXCEPT ![e] = TRUE]
    /\ UNCHANGED <<active, inactive, campaign, culprit>>

TrialFail(e) ==
    /\ campaign = "run" /\ stage[e] = "trial"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ UNCHANGED <<active, inactive, corrupt>>

PowerLoss ==
    /\ campaign \in {"run", "rollback"}
    /\ stage' = [e \in ECUs |-> IF stage[e] = "downloaded" THEN "idle" ELSE stage[e]]
    /\ corrupt' = [e \in ECUs |-> IF stage[e] = "downloaded" THEN FALSE ELSE corrupt[e]]
    /\ campaign' = "rollback"
    /\ UNCHANGED <<active, inactive, culprit>>

\* A failure somewhere else in the vehicle.
EnvFail ==
    /\ EnvEnabled
    /\ campaign = "run"
    /\ campaign' = "rollback"
    /\ UNCHANGED <<active, inactive, stage, corrupt, culprit>>

RollbackScope == IF Flaw = "LocalRollback" THEN culprit ELSE ECUs

RollbackOrderOK(e) ==
    \/ Flaw = "LocalRollback"
    \/ \A dep \in Deps : dep[2] = e => active[dep[1]] = 1

Rollback(e) ==
    /\ campaign = "rollback"
    /\ e \in RollbackScope
    /\ active[e] = 2 /\ inactive[e] = 1
    /\ RollbackOrderOK(e)
    /\ active' = [active EXCEPT ![e] = 1]
    /\ inactive' = [inactive EXCEPT ![e] = 2]
    /\ stage' = [stage EXCEPT ![e] = "reverted"]
    /\ UNCHANGED <<corrupt, campaign, culprit>>

FinishRollback ==
    /\ campaign = "rollback"
    /\ \A e \in RollbackScope : active[e] = 1
    /\ campaign' = "aborted"
    /\ UNCHANGED <<active, inactive, stage, corrupt, culprit>>

Next ==
    \/ \E e \in ECUs :
        \/ Download(e) \/ Verify(e) \/ VerifyReject(e) \/ Activate(e) \/ Confirm(e)
        \/ DownloadFail(e) \/ DownloadCorrupt(e) \/ TrialFail(e) \/ Rollback(e)
    \/ Commit \/ PowerLoss \/ EnvFail \/ FinishRollback

\* No fairness: this abstraction supports safety properties only.
Safe == Init /\ [][Next]_vars

CompatAlways == \A dep \in Deps : active[dep[1]] = 2 => active[dep[2]] = 2

WayBackKept ==
    campaign /= "committed" => \A e \in ECUs : active[e] = 2 => inactive[e] = 1

AllOrNothing ==
    campaign \in Ended =>
        \/ \A e \in ECUs : active[e] = 2
        \/ \A e \in ECUs : active[e] = 1

OnlyVerifiedRuns == \A e \in ECUs : active[e] = 2 => ~corrupt[e]
====
