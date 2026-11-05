"""Explicit v2 operational tables; never applied by ordinary workspace opening."""
SCHEMA_V2 = (
    '''CREATE TABLE ota_review_auth (
       run_id TEXT NOT NULL, revision INTEGER NOT NULL, identity_json TEXT NOT NULL,
       roles_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
       PRIMARY KEY(run_id,revision), FOREIGN KEY(run_id,revision) REFERENCES ota_decisions(run_id,revision))''',
    '''CREATE TABLE ota_retention (
       run_id TEXT PRIMARY KEY REFERENCES ota_runs(run_id), archived_at TEXT NOT NULL,
       actor TEXT NOT NULL, reason TEXT NOT NULL)''',
    '''CREATE TABLE ota_migrations (
       version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, backup_sha256 TEXT NOT NULL)''',
)
REQUIRED_V2 = {'ota_review_auth', 'ota_retention', 'ota_migrations'}
