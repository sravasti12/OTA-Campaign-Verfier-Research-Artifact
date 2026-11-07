---- MODULE Refine_n3_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02"}
GenDeps == {<<"ecu01", "ecu00">>}
CONSTANT EnvOn
P0 == INSTANCE OTAPair WITH ECUs <- {"ecu00", "ecu01"}, Deps <- {<<"ecu01", "ecu00">>}, Flaw <- Flaw,
    EnvEnabled <- EnvOn,
    active <- [e \in {"ecu00", "ecu01"} |-> active[e]],
    inactive <- [e \in {"ecu00", "ecu01"} |-> inactive[e]],
    stage <- [e \in {"ecu00", "ecu01"} |-> stage[e]],
    corrupt <- [e \in {"ecu00", "ecu01"} |-> corrupt[e]],
    campaign <- campaign, culprit <- culprit \cap {"ecu00", "ecu01"}
R0 == P0!Safe
P1 == INSTANCE OTAPair WITH ECUs <- {"ecu00", "ecu02"}, Deps <- {}, Flaw <- Flaw,
    EnvEnabled <- EnvOn,
    active <- [e \in {"ecu00", "ecu02"} |-> active[e]],
    inactive <- [e \in {"ecu00", "ecu02"} |-> inactive[e]],
    stage <- [e \in {"ecu00", "ecu02"} |-> stage[e]],
    corrupt <- [e \in {"ecu00", "ecu02"} |-> corrupt[e]],
    campaign <- campaign, culprit <- culprit \cap {"ecu00", "ecu02"}
R1 == P1!Safe
P2 == INSTANCE OTAPair WITH ECUs <- {"ecu01", "ecu02"}, Deps <- {}, Flaw <- Flaw,
    EnvEnabled <- EnvOn,
    active <- [e \in {"ecu01", "ecu02"} |-> active[e]],
    inactive <- [e \in {"ecu01", "ecu02"} |-> inactive[e]],
    stage <- [e \in {"ecu01", "ecu02"} |-> stage[e]],
    corrupt <- [e \in {"ecu01", "ecu02"} |-> corrupt[e]],
    campaign <- campaign, culprit <- culprit \cap {"ecu01", "ecu02"}
R2 == P2!Safe
====
