# EarlyErase__L1__F1

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | Download | gateway | v1 downloaded, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 3 | DownloadCorrupt | brake | v1 downloaded, spare v0 | v1 downloaded (corrupt), spare v0 | v1 idle, spare v0 | run | 1 |
| 4 | Download | infotainment | v1 downloaded, spare v0 | v1 downloaded (corrupt), spare v0 | v1 downloaded, spare v0 | run | 1 |
| 5 | Verify | infotainment | v1 downloaded, spare v0 | v1 downloaded (corrupt), spare v0 | v1 verified, spare v2 | run | 1 |
| 6 | Verify | gateway | v1 verified, spare v2 | v1 downloaded (corrupt), spare v0 | v1 verified, spare v2 | run | 1 |
| 7 | Activate | gateway | v2 trial, spare v0 | v1 downloaded (corrupt), spare v0 | v1 verified, spare v2 | run | 1 |
| 8 | Confirm | gateway | v2 healthy, spare v0 | v1 downloaded (corrupt), spare v0 | v1 verified, spare v2 | run | 1 |
| 9 | Activate | infotainment | v2 healthy, spare v0 | v1 downloaded (corrupt), spare v0 | v2 trial, spare v0 | run | 1 |
| 10 | Confirm | infotainment | v2 healthy, spare v0 | v1 downloaded (corrupt), spare v0 | v2 healthy, spare v0 | run | 1 |
| 11 | VerifyReject | brake | v2 healthy, spare v0 | v1 failed (corrupt), spare v0 | v2 healthy, spare v0 | rollback | 1 |

The system then stays in the last state forever.
