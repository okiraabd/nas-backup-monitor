import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from kopia_reporter import (  # noqa: E402
    ReporterConfig,
    build_login_payload,
    extract_access_token,
    normalize_snapshot,
    reconcile_snapshots,
)


FIXTURE = Path(__file__).parent / "fixtures" / "kopia_snapshot_list.json"

WD_SNAPSHOT = {
    "id": "b5d4465116af802fbe2c16d759743c4c",
    "source": {
        "host": "451684be308e",
        "userName": "root",
        "path": "/MAKUKU",
    },
    "description": "",
    "startTime": "2026-06-21T10:10:22.04032575Z",
    "endTime": "2026-06-21T11:10:53.088149575Z",
    "stats": {
        "totalSize": 154241124981,
        "fileCount": 11444,
        "cachedFiles": 176,
        "nonCachedFiles": 11403,
        "dirCount": 43,
        "ignoredErrorCount": 0,
        "errorCount": 0,
    },
    "rootEntry": {
        "name": "MAKUKU",
        "type": "d",
        "summ": {
            "size": 154241124981,
            "files": 11579,
            "dirs": 43,
            "numFailed": 0,
        },
    },
    "retentionReason": ["latest-9", "weekly-2", "monthly-2"],
}


class KopiaReporterTests(unittest.TestCase):
    def setUp(self):
        self.snapshots = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.config = ReporterConfig(nas_id="synology-ds1522")

    def test_normalize_autoderives_job_and_source_path(self):
        payload = normalize_snapshot(self.snapshots[-1], self.config)

        self.assertEqual(payload["nas_id"], "synology-ds1522")
        self.assertEqual(payload["job_name"], "backup-hr")
        self.assertEqual(payload["source_path"], "/master_backup/hr")
        self.assertIsNone(payload["source_ip"])
        self.assertIsNone(payload["destination_target"])
        self.assertEqual(payload["status"], "SUCCESS")
        self.assertEqual(payload["duration_seconds"], 1)
        self.assertEqual(payload["total_size_bytes"], 38189013)
        self.assertEqual(payload["total_files"], 30)
        self.assertEqual(payload["changed_file_count"], 0)
        self.assertEqual(payload["snapshot_id"], self.snapshots[-1]["id"])

    def test_wd_snapshot_autoderives_job_without_per_job_config(self):
        payload = normalize_snapshot(
            WD_SNAPSHOT,
            ReporterConfig(nas_id="mycloudmakuku"),
        )

        self.assertEqual(payload["job_name"], "backup-makuku")
        self.assertEqual(payload["source_path"], "/MAKUKU")
        self.assertEqual(payload["total_size_bytes"], 154241124981)
        self.assertEqual(payload["total_files"], 11579)
        self.assertEqual(payload["raw_payload"]["source"]["host"], "451684be308e")

    def test_snapshot_errors_map_to_failed(self):
        snapshot = deepcopy(self.snapshots[-1])
        snapshot["stats"]["errorCount"] = 2

        payload = normalize_snapshot(snapshot, self.config)

        self.assertEqual(payload["status"], "FAILED")
        self.assertEqual(payload["error_count"], 2)

    def test_initial_latest_queues_newest_snapshot_per_source(self):
        finance_old = deepcopy(self.snapshots[0])
        finance_old["id"] = "finance-old"
        finance_old["source"]["path"] = "/master_backup/finance"
        finance_old["rootEntry"]["name"] = "finance"
        finance_old["startTime"] = "2026-07-08T06:01:00.000000001Z"
        finance_old["endTime"] = "2026-07-08T06:01:00.000000002Z"

        finance_new = deepcopy(finance_old)
        finance_new["id"] = "finance-new"
        finance_new["startTime"] = "2026-07-08T06:11:00.000000001Z"
        finance_new["endTime"] = "2026-07-08T06:11:00.000000002Z"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "state.json"
            pending = root / "pending"

            first = reconcile_snapshots(
                [*self.snapshots, finance_old, finance_new],
                config=self.config,
                state_path=state,
                pending_dir=pending,
            )
            repeated = reconcile_snapshots(
                [*self.snapshots, finance_old, finance_new],
                config=self.config,
                state_path=state,
                pending_dir=pending,
            )

            pending_names = sorted(path.name for path in pending.glob("*.json"))

            self.assertEqual(first["sources"], 2)
            self.assertEqual(first["created"], 2)
            self.assertEqual(repeated["unseen"], 0)
            self.assertEqual(len(pending_names), 2)
            self.assertTrue(any("backup-hr" in name for name in pending_names))
            self.assertTrue(any("backup-finance" in name for name in pending_names))

    def test_existing_pending_file_is_not_overwritten_after_state_loss(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending = root / "pending"
            first_state = root / "first-state.json"
            rebuilt_state = root / "rebuilt-state.json"

            first = reconcile_snapshots(
                self.snapshots,
                config=self.config,
                state_path=first_state,
                pending_dir=pending,
            )
            retry = reconcile_snapshots(
                self.snapshots,
                config=self.config,
                state_path=rebuilt_state,
                pending_dir=pending,
            )

            self.assertEqual(first["created"], 1)
            self.assertEqual(retry["created"], 0)
            self.assertEqual(retry["already_pending"], 1)

    def test_login_payload_preserves_special_characters(self):
        payload = build_login_payload("nas-service\0p@ss word!$\\n".encode())

        self.assertEqual(payload["username"], "nas-service")
        self.assertEqual(payload["password"], "p@ss word!$\\n")

    def test_extract_access_token(self):
        self.assertEqual(extract_access_token({"access_token": "jwt-value"}), "jwt-value")

    def test_extract_access_token_rejects_missing_token(self):
        with self.assertRaises(ValueError):
            extract_access_token({"token_type": "bearer"})


if __name__ == "__main__":
    unittest.main()
