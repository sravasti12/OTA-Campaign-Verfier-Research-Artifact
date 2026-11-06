# EarlyErase__L1__F2

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | DownloadCorrupt | gateway | v1 downloaded (corrupt), spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 1 |
| 3 | DownloadCorrupt | brake | v1 downloaded (corrupt), spare v0 | v1 downloaded (corrupt), spare v0 | v1 idle, spare v0 | run | 2 |
| 4 | Download | infotainment | v1 downloaded (corrupt), spare v0 | v1 downloaded (corrupt), spare v0 | v1 downloaded, spare v0 | run | 2 |
| 5 | Verify | infotainment | v1 downloaded (corrupt), spare v0 | v1 downloaded (corrupt), spare v0 | v1 verified, spare v2 | run | 2 |
| 6 | Activate | infotainment | v1 downloaded (corrupt), spare v0 | v1 downloaded (corrupt), spare v0 | v2 trial, spare v0 | run | 2 |
| 7 | VerifyReject | brake | v1 downloaded (corrupt), spare v0 | v1 failed (corrupt), spare v0 | v2 trial, spare v0 | rollback | 2 |

The system then stays in the last state forever.
