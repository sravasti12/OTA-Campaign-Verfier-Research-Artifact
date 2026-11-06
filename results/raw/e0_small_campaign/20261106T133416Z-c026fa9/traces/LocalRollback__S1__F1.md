# LocalRollback__S1__F1

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | Download | gateway | v1 downloaded, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 3 | Verify | gateway | v1 verified, spare v2 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 4 | Activate | gateway | v2 trial, spare v1 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 5 | Download | brake | v2 trial, spare v1 | v1 downloaded, spare v0 | v1 idle, spare v0 | run | 0 |
| 6 | Verify | brake | v2 trial, spare v1 | v1 verified, spare v2 | v1 idle, spare v0 | run | 0 |
| 7 | Activate | brake | v2 trial, spare v1 | v2 trial, spare v1 | v1 idle, spare v0 | run | 0 |
| 8 | TrialFail | gateway | v2 failed, spare v1 | v2 trial, spare v1 | v1 idle, spare v0 | rollback | 1 |
| 9 | Rollback | gateway | v1 reverted, spare v2 | v2 trial, spare v1 | v1 idle, spare v0 | rollback | 1 |
