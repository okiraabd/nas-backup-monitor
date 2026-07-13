// TypeScript shapes for the API responses, mirroring the backend Pydantic
// schemas in api/app/schemas/. These replace `any` on the query/mutation layer
// so field typos are caught at build time. Optional fields use `?` because the
// backend omits/nulls them in several responses.

// --- Auth / users (api/app/schemas/user.py, auth) ---
export interface User {
  id: number;
  username: string;
  display_name: string;
  role: string;
}

export interface UserOut extends User {
  is_active: boolean;
  created_by?: number | null;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RotateTokenResponse {
  user_id: number;
  username: string;
  new_password: string;
  message: string;
}

// --- Backup logs (api/app/schemas/log.py) ---
export interface BackupLogSummary {
  id: number;
  nas_id: string;
  job_name: string;
  status: string;
  snapshot_id?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  duration_seconds?: number | null;
  total_size_bytes?: number | null;
  error_count?: number | null;
  acknowledged: boolean;
  created_at: string;
}

export interface BackupLogDetail extends BackupLogSummary {
  source_path?: string | null;
  source_ip?: string | null;
  destination_target?: string | null;
  backup_engine: string;
  total_files?: number | null;
  changed_file_count?: number | null;
  cached_files?: number | null;
  non_cached_files?: number | null;
  dir_count?: number | null;
  ignored_error_count?: number | null;
  retention_reason?: unknown[] | null;
  message?: string | null;
  raw_payload?: Record<string, unknown> | null;
  reported_by?: number | null;
  acknowledged_by?: number | null;
  acknowledged_at?: string | null;
  remark?: string | null;
}

export interface PaginatedLogs {
  items: BackupLogSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// --- Monitoring (api/app/schemas/monitor.py) ---
export interface MetricValue {
  value?: number | null;
  text?: string | null;
  unit?: string | null;
}

export interface SourceSnapshot {
  source_id: string;
  display_name: string;
  source_type: string;
  last_collected_at?: string | null;
  staleness_seconds?: number | null;
  status: string;
  metrics: Record<string, MetricValue>;
}

export interface NasListResponse {
  items: SourceSnapshot[];
}

export interface HistoryPoint {
  collected_at: string;
  value?: number | null;
  text?: string | null;
}

export interface MetricHistory {
  source_id: string;
  metric_name: string;
  points: HistoryPoint[];
}

export interface MonitorSummary {
  total_nas: number;
  nas_fresh: number;
  nas_stale: number;
  nas_offline: number;
  ceph_status: string;
  ceph_health?: string | null;
  storage_used_pct?: number | null;
}

export interface CollectorStatus {
  last_run_at?: string | null;
  last_status?: string | null;
  is_mock: boolean;
  total_sources: number;
  success_sources: number;
  failed_sources: number;
  message?: string | null;
}

export interface ActivityDay {
  date: string;
  success: number;
  failed: number;
}

export interface ActivityTrendResponse {
  days: ActivityDay[];
}

// --- Reports (api/app/schemas/report.py) ---
export interface Report {
  id: number;
  filename: string;
  date_from: string;
  date_to: string;
  nas_filter?: string | null;
  generated_by?: number | null;
  generated_at: string;
  file_size_bytes?: number | null;
}

// --- Shared ---
export interface BulkDeleteResponse {
  deleted_count: number;
}
