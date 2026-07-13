import { Clock, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AUTO_REFRESH_OPTIONS } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface AutoRefreshControlProps {
  /** Current interval in milliseconds; 0 means off. */
  valueMs: number;
  /** Called with the new interval in milliseconds. */
  onChangeMs: (ms: number) => void;
  onRefresh: () => void;
  isFetching: boolean;
  /** TanStack Query dataUpdatedAt timestamp (ms epoch); 0 hides the label. */
  lastUpdatedAt?: number;
  className?: string;
}

/**
 * "Last updated + auto-refresh interval + manual refresh" control shared by the
 * dashboard/monitoring pages. Interval is always handled in milliseconds.
 */
export function AutoRefreshControl({
  valueMs,
  onChangeMs,
  onRefresh,
  isFetching,
  lastUpdatedAt = 0,
  className,
}: AutoRefreshControlProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 text-sm text-muted-foreground hidden lg:flex",
        className,
      )}
    >
      {lastUpdatedAt > 0 && (
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Last updated: {new Date(lastUpdatedAt).toLocaleTimeString()}
        </span>
      )}
      <div className="flex items-center gap-2 border-l pl-4 border-border">
        <span className="text-xs">Auto Refresh:</span>
        <Select value={valueMs.toString()} onValueChange={(v) => onChangeMs(Number(v))}>
          <SelectTrigger className="h-8 w-[80px] text-xs bg-background">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AUTO_REFRESH_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value.toString()}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 bg-background"
          onClick={onRefresh}
          disabled={isFetching}
          title="Refresh Now"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
        </Button>
      </div>
    </div>
  );
}
