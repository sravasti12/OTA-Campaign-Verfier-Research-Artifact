---- MODULE OTACampaign ----
\* A multi-ECU A/B update campaign. Plain-English definitions: specs/SMALL_CAMPAIGN.md
EXTENDS Naturals

CONSTANTS
    ECUs,       \* the ECUs being updated from version 1 to version 2
    Deps,       \* set of <<x, d>>: version 2 of x requires version 2 of d
    MaxFaults,  \* bound on injected faults
    Flaw        \* "none", "LocalRollback", "EarlyErase" or "SkipVerify"

VARIABLES
    active,     \* version each ECU runs: 1 or 2
    inactive,   \* valid version held in the other slot: 0 means none
    stage,      \* per-ECU progress
    corrupt,    \* the downloaded image is damaged
    campaign,   \* "run", "rollback", "committed" or "aborted"
    culprit,    \* ECUs that reported a failure
    faults      \* faults injected so far

vars == <<active, inactive, stage, corrupt, campaign, culprit, faults>>

Stages == {"idle", "downloaded", "verified", "trial", "healthy", "failed", "reverted"}
Ended == {"committed", "aborted"}

TypeOK ==
    /\ active \in [ECUs -> {1, 2}]
    /\ inactive \in [ECUs -> {0, 1, 2}]
    /\ stage \in [ECUs -> Stages]
    /\ corrupt \in [ECUs -> BOOLEAN]
    /\ campaign \in {"run", "rollback"} \cup Ended
    /\ culprit \subseteq ECUs
    /\ faults \in 0..MaxFaults

Init ==
    /\ active = [e \in ECUs |-> 1]
    /\ inactive = [e \in ECUs |-> 0]
    /\ stage = [e \in ECUs |-> "idle"]
    /\ corrupt = [e \in ECUs |-> FALSE]
    /\ campaign = "run"
    /\ culprit = {}
    /\ faults = 0

\* ---- Nominal steps ----

Download(e) ==
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "downloaded"]
    /\ UNCHANGED <<active, inactive, corrupt, campaign, culprit, faults>>

Verify(e) ==
    /\ campaign = "run" /\ stage[e] = "downloaded"
    /\ ~corrupt[e] \/ Flaw = "SkipVerify"
    /\ stage' = [stage EXCEPT ![e] = "verified"]
    /\ inactive' = [inactive EXCEPT ![e] = 2]
    /\ UNCHANGED <<active, corrupt, campaign, culprit, faults>>

VerifyReject(e) ==
    /\ campaign = "run" /\ stage[e] = "downloaded"
    /\ corrupt[e] /\ Flaw /= "SkipVerify"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ UNCHANGED <<active, inactive, corrupt, faults>>

\* Activation order is enforced in every design: dependencies go first.
Activate(e) ==
    /\ campaign = "run" /\ stage[e] = "verified"
    /\ \A dep \in Deps : dep[1] = e => active[dep[2]] = 2
    /\ active' = [active EXCEPT ![e] = 2]
    /\ inactive' = [inactive EXCEPT ![e] = IF Flaw = "EarlyErase" THEN 0 ELSE 1]
    /\ stage' = [stage EXCEPT ![e] = "trial"]
    /\ UNCHANGED <<corrupt, campaign, culprit, faults>>

Confirm(e) ==
    /\ campaign = "run" /\ stage[e] = "trial"
    /\ stage' = [stage EXCEPT ![e] = "healthy"]
    /\ UNCHANGED <<active, inactive, corrupt, campaign, culprit, faults>>

Commit ==
    /\ campaign = "run"
    /\ \A e \in ECUs : stage[e] = "healthy"
    /\ campaign' = "committed"
    /\ UNCHANGED <<active, inactive, stage, corrupt, culprit, faults>>

\* ---- Faults ----

DownloadFail(e) ==
    /\ faults < MaxFaults
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ faults' = faults + 1
    /\ UNCHANGED <<active, inactive, corrupt>>

DownloadCorrupt(e) ==
    /\ faults < MaxFaults
    /\ campaign = "run" /\ stage[e] = "idle"
    /\ stage' = [stage EXCEPT ![e] = "downloaded"]
    /\ corrupt' = [corrupt EXCEPT ![e] = TRUE]
    /\ faults' = faults + 1
    /\ UNCHANGED <<active, inactive, campaign, culprit>>

TrialFail(e) ==
    /\ faults < MaxFaults
    /\ campaign = "run" /\ stage[e] = "trial"
    /\ stage' = [stage EXCEPT ![e] = "failed"]
    /\ campaign' = "rollback"
    /\ culprit' = culprit \cup {e}
    /\ faults' = faults + 1
    /\ UNCHANGED <<active, inactive, corrupt>>

\* Unverified downloads are lost. Campaign state is assumed durable.
PowerLoss ==
    /\ faults < MaxFaults
    /\ campaign \in {"run", "rollback"}
    /\ stage' = [e \in ECUs |-> IF stage[e] = "downloaded" THEN "idle" ELSE stage[e]]
    /\ corrupt' = [e \in ECUs |-> IF stage[e] = "downloaded" THEN FALSE ELSE corrupt[e]]
    /\ campaign' = "rollback"
    /\ faults' = faults + 1
    /\ UNCHANGED <<active, inactive, culprit>>

\* ---- Rollback ----

RollbackScope == IF Flaw = "LocalRollback" THEN culprit ELSE ECUs

\* Correct design: an ECU reverts only after everything depending on it has.
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
    /\ UNCHANGED <<corrupt, campaign, culprit, faults>>

FinishRollback ==
    /\ campaign = "rollback"
    /\ \A e \in RollbackScope : active[e] = 1
    /\ campaign' = "aborted"
    /\ UNCHANGED <<active, inactive, stage, corrupt, culprit, faults>>

\* ---- Specification ----

Next ==
    \/ \E e \in ECUs :
        \/ Download(e) \/ Verify(e) \/ VerifyReject(e) \/ Activate(e) \/ Confirm(e)
        \/ DownloadFail(e) \/ DownloadCorrupt(e) \/ TrialFail(e) \/ Rollback(e)
    \/ Commit \/ PowerLoss \/ FinishRollback

\* Steps that can run eventually do. Faults are never forced to happen.
Fairness ==
    /\ \A e \in ECUs :
        /\ WF_vars(Download(e)) /\ WF_vars(Verify(e)) /\ WF_vars(VerifyReject(e))
        /\ WF_vars(Activate(e)) /\ WF_vars(Confirm(e)) /\ WF_vars(Rollback(e))
    /\ WF_vars(Commit) /\ WF_vars(FinishRollback)

Spec == Init /\ [][Next]_vars /\ Fairness

\* ---- Properties ----

\* S1. Compatible at all times.
CompatAlways == \A dep \in Deps : active[dep[1]] = 2 => active[dep[2]] = 2

\* S2. A way back is kept.
WayBackKept ==
    campaign /= "committed" => \A e \in ECUs : active[e] = 2 => inactive[e] = 1

\* S3. All or nothing.
AllOrNothing ==
    campaign \in Ended =>
        \/ \A e \in ECUs : active[e] = 2
        \/ \A e \in ECUs : active[e] = 1

\* S4. Only verified images run.
OnlyVerifiedRuns == \A e \in ECUs : active[e] = 2 => ~corrupt[e]

\* L1. The campaign always finishes.
CampaignFinishes == <>(campaign \in Ended)

\* ---- Sanity checks: these are expected to be violated in the correct design ----
\* If one held, the properties above could be passing only because nothing happens.

NeverCommits == campaign /= "committed"
NeverAborts == campaign /= "aborted"
NeverRevertsAnything == \A e \in ECUs : stage[e] /= "reverted"
====
