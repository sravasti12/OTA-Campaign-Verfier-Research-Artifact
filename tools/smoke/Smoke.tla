---- MODULE Smoke ----
\* Toolchain check only. Not a model of an OTA campaign.
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x < 3 /\ x' = x + 1
Spec == Init /\ [][Next]_x
Holds == x <= 3
Fails == x < 3
====
