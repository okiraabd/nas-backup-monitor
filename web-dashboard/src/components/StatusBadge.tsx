import { CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { STATUS_COLORS } from "@/lib/status";

/**
 * Backup status badge (SUCCESS / FAILED) with the shared status colors and
 * icons. Any other status falls back to a neutral outline badge.
 */
export function BackupStatusBadge({ status }: { status: string }) {
  if (status === "SUCCESS") {
    return (
      <Badge variant="outline" className={STATUS_COLORS.success}>
        <CheckCircle2 className="w-3 h-3 mr-1" /> SUCCESS
      </Badge>
    );
  }
  if (status === "FAILED") {
    return (
      <Badge variant="outline" className={STATUS_COLORS.danger}>
        <XCircle className="w-3 h-3 mr-1" /> FAILED
      </Badge>
    );
  }
  return <Badge variant="outline">{status}</Badge>;
}
