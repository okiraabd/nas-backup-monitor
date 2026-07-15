import os
import time
import logging
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

from snmp_collector import get_mock_nas_metrics, get_snmp_nas_metrics
from ceph_collector import get_mock_ceph_metrics, get_prometheus_ceph_metrics

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load env
load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000/api")
USERNAME = os.getenv("COLLECTOR_USERNAME", "collector")
PASSWORD = os.getenv("COLLECTOR_PASSWORD", "collector123")
INTERVAL = int(os.getenv("COLLECTOR_INTERVAL_SECONDS", 10))
USE_MOCK_METRICS = os.getenv("USE_MOCK_METRICS", "false").lower() == "true"
SNMP_EXPORTER_URL = os.getenv("SNMP_EXPORTER_URL", "").strip() or None
SNMP_DEFAULT_MODULE = os.getenv("SNMP_DEFAULT_MODULE", "if_mib").strip()
NAS_TARGETS_STR = os.getenv(
    "NAS_TARGETS",
    "synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100",
)
CEPH_METRICS_URL = os.getenv("CEPH_METRICS_URL", "http://192.168.24.6:9283/metrics")

class MetricCollector:
    def __init__(self):
        self.api_url = API_URL
        self.username = USERNAME
        self.password = PASSWORD
        self.interval = INTERVAL
        self.use_mock_metrics = USE_MOCK_METRICS
        self.token = None
        self.nas_targets = self._parse_nas_targets(NAS_TARGETS_STR)

    def _parse_nas_targets(self, raw_targets: str) -> list[dict]:
        """Parse NAS_TARGETS into source id, IP, exporter module, and profile.

        Preferred format:
            source_id|ip_address|module_name

        Legacy format is still accepted for compatibility:
            source_id:ip_address
        """
        targets = []
        for raw_target in raw_targets.split(","):
            target = raw_target.strip()
            if not target:
                continue

            if "|" in target:
                parts = [part.strip() for part in target.split("|")]
                if len(parts) < 2 or not parts[0] or not parts[1]:
                    logger.warning("Skipping invalid NAS target: %s", target)
                    continue
                source_id = parts[0]
                ip = parts[1]
                module = parts[2] if len(parts) >= 3 and parts[2] else SNMP_DEFAULT_MODULE
                profile = parts[3] if len(parts) >= 4 and parts[3] else None
            elif ":" in target:
                source_id, ip = [part.strip() for part in target.split(":", 1)]
                module = SNMP_DEFAULT_MODULE
                profile = None
            else:
                logger.warning("Skipping invalid NAS target: %s", target)
                continue

            targets.append({"id": source_id, "ip": ip, "module": module, "profile": profile})

        return targets

    def login(self):
        """Login to the API to obtain JWT token."""
        logger.info(f"Logging in to {self.api_url}/auth/login")
        try:
            res = httpx.post(f"{self.api_url}/auth/login", json={
                "username": self.username,
                "password": self.password
            }, timeout=10)
            res.raise_for_status()
            self.token = res.json()["access_token"]
            logger.info("Login successful.")
            return True
        except Exception as e:
            logger.error(f"Failed to login: {e}")
            return False

    def ingest_metrics(self, payload: dict) -> bool:
        """Post a metric payload to the API."""
        if not self.token:
            logger.error("No token available.")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res = httpx.post(
                f"{self.api_url}/monitor/ingest", 
                json=payload, 
                headers=headers,
                timeout=10
            )
            if res.status_code == 401:
                logger.warning("Token expired. Re-login required.")
                self.token = None
                return False
            res.raise_for_status()
            logger.info(f"Ingested metrics for {payload.get('source_id')} -> {res.json().get('stored_metrics')} metrics stored.")
            return True
        except Exception as e:
            logger.error(f"Failed to ingest metrics for {payload.get('source_id')}: {e}")
            return False

    def report_run_status(self, run_info: dict):
        """Report the completion status of a collector run."""
        if not self.token:
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res = httpx.post(
                f"{self.api_url}/monitor/collector/run", 
                json=run_info, 
                headers=headers,
                timeout=10
            )
            res.raise_for_status()
            logger.info(f"Reported collector run status: {run_info.get('status')}")
        except Exception as e:
            logger.error(f"Failed to report run status: {e}")

    def run_once(self):
        """Execute one cycle of metrics collection."""
        if not self.token and not self.login():
            return

        run_start = datetime.now(timezone.utc)
        success_count = 0
        failed_count = 0
        total_count = len(self.nas_targets) + 1  # NAS + Ceph
        
        now_str = datetime.now(timezone.utc).isoformat()
        
        # 1. Collect NAS metrics
        for nas in self.nas_targets:
            try:
                if self.use_mock_metrics:
                    metrics = get_mock_nas_metrics(nas["id"])
                else:
                    metrics = get_snmp_nas_metrics(
                        nas["id"],
                        nas["ip"],
                        exporter_url=SNMP_EXPORTER_URL,
                        module=nas.get("module"),
                        profile=nas.get("profile"),
                    )
                
                payload = {
                    "source_type": "nas",
                    "source_id": nas["id"],
                    "collected_at": now_str,
                    "metrics": metrics
                }
                
                if self.ingest_metrics(payload):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error collecting NAS {nas['id']}: {e}")
                failed_count += 1

        # 2. Collect Ceph metrics
        try:
            if self.use_mock_metrics:
                metrics = get_mock_ceph_metrics("ceph-cluster")
            else:
                metrics = get_prometheus_ceph_metrics(CEPH_METRICS_URL)
                
            payload = {
                "source_type": "ceph",
                "source_id": "ceph-cluster",
                "collected_at": now_str,
                "metrics": metrics
            }
            
            if self.ingest_metrics(payload):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Error collecting Ceph: {e}")
            failed_count += 1

        run_finish = datetime.now(timezone.utc)
        
        # Report run status
        status = "SUCCESS" if failed_count == 0 else "PARTIAL_FAILED"
        if success_count == 0:
            status = "FAILED"
            
        self.report_run_status({
            "started_at": run_start.isoformat(),
            "finished_at": run_finish.isoformat(),
            "status": status,
            "is_mock": self.use_mock_metrics,
            "total_sources": total_count,
            "success_sources": success_count,
            "failed_sources": failed_count,
            "message": f"Collected metrics from {success_count} sources."
        })

    def check_pending_run(self):
        """Check if there is a pending manual run requested."""
        if not self.token:
            return False
        try:
            res = httpx.get(
                f"{self.api_url}/monitor/collector/status",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
            if res.status_code == 200:
                return res.json().get("last_status") == "PENDING"
        except Exception:
            pass
        return False

    def start(self):
        exporter_mode = "centralized" if SNMP_EXPORTER_URL else "legacy-per-nas"
        logger.info(
            "Starting Collector (Mock=%s, SNMP=%s). Interval: %ss",
            self.use_mock_metrics,
            exporter_mode,
            self.interval,
        )
        while True:
            self.run_once()
            
            # Wait for interval, but check for manual runs every 2 seconds
            wait_time = 0
            while wait_time < self.interval:
                time.sleep(2)
                wait_time += 2
                if self.check_pending_run():
                    logger.info("Detected PENDING manual run. Triggering immediate collection.")
                    break

if __name__ == "__main__":
    collector = MetricCollector()
    collector.start()
