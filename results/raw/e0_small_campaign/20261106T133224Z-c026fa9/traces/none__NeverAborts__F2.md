# none__NeverAborts__F2

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | DownloadFail | gateway | v1 failed, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | rollback | 1 |
| 3 | FinishRollback |  | v1 failed, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | aborted | 1 |
