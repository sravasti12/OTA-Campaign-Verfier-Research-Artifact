# SkipVerify__S4__F2

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | DownloadCorrupt | gateway | v1 downloaded (corrupt), spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 1 |
| 3 | Verify | gateway | v1 verified (corrupt), spare v2 | v1 idle, spare v0 | v1 idle, spare v0 | run | 1 |
| 4 | Activate | gateway | v2 trial (corrupt), spare v1 | v1 idle, spare v0 | v1 idle, spare v0 | run | 1 |
