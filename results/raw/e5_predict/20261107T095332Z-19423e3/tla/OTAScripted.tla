---- MODULE OTAScripted ----
\* OTACampaign pinned to one schedule and one fault script, so the model predicts a single
\* path. The actions are OTACampaign's own. Each path is reported with PrintT when it halts.
EXTENDS OTACampaign, Sequences, TLC

CONSTANTS
    Priority,   \* sequence of <<action, ecu>>: the first enabled one runs
    Scripts     \* set of [id, faults]; faults is a set of [tick, kind, ecu]

VARIABLES sid, plan, tick, log, seen, halted

all == <<vars, sid, plan, tick, log, seen, halted>>

Do(a) ==
    CASE a[1] = "Download" -> Download(a[2])
      [] a[1] = "Verify" -> Verify(a[2])
      [] a[1] = "VerifyReject" -> VerifyReject(a[2])
      [] a[1] = "Activate" -> Activate(a[2])
      [] a[1] = "Confirm" -> Confirm(a[2])
      [] a[1] = "Rollback" -> Rollback(a[2])
      [] a[1] = "DownloadFail" -> DownloadFail(a[2])
      [] a[1] = "DownloadCorrupt" -> DownloadCorrupt(a[2])
      [] a[1] = "TrialFail" -> TrialFail(a[2])
      [] a[1] = "Commit" -> Commit
      [] a[1] = "FinishRollback" -> FinishRollback
      [] a[1] = "PowerLoss" -> PowerLoss

DueFaults == {f \in plan : f.tick = tick /\ ENABLED Do(<<f.kind, f.ecu>>)}

EnabledSteps == {i \in 1..Len(Priority) : ENABLED Do(Priority[i])}

Chosen ==
    IF DueFaults /= {}
    THEN LET f == CHOOSE x \in DueFaults : TRUE IN <<f.kind, f.ecu>>
    ELSE IF EnabledSteps = {}
         THEN <<"Halt", "">>
         ELSE Priority[CHOOSE i \in EnabledSteps : \A j \in EnabledSteps : i <= j]

Violated ==
    (IF CompatAlways THEN {} ELSE {"S1"}) \cup (IF WayBackKept THEN {} ELSE {"S2"})
    \cup (IF AllOrNothing THEN {} ELSE {"S3"}) \cup (IF OnlyVerifiedRuns THEN {} ELSE {"S4"})

SInit ==
    /\ Init
    /\ \E s \in Scripts : sid = s.id /\ plan = s.faults
    /\ tick = 0
    /\ log = <<>>
    /\ seen = {}
    /\ halted = FALSE

SNext ==
    /\ ~halted
    /\ LET a == Chosen IN
        IF a[1] = "Halt"
        THEN /\ halted' = TRUE
             /\ UNCHANGED <<vars, sid, plan, tick, log, seen>>
        ELSE /\ Do(a)
             /\ tick' = tick + 1
             /\ log' = Append(log, a)
             /\ seen' = seen \cup Violated'
             /\ halted' = FALSE
             /\ UNCHANGED <<sid, plan>>

SSpec == SInit /\ [][SNext]_all

Report == halted => PrintT(<<"RESULT", sid, seen, campaign, active, log>>)
====
