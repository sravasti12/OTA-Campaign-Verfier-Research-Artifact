# LocalRollback__S3__F1

| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Initial |  | v1 idle, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 2 | Download | gateway | v1 downloaded, spare v0 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 3 | Verify | gateway | v1 verified, spare v2 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 4 | Activate | gateway | v2 trial, spare v1 | v1 idle, spare v0 | v1 idle, spare v0 | run | 0 |
| 5 | DownloadFail | brake | v2 trial, spare v1 | v1 failed, spare v0 | v1 idle, spare v0 | rollback | 1 |
| 6 | FinishRollback |  | v2 trial, spare v1 | v1 failed, spare v0 | v1 idle, spare v0 | aborted | 1 |
