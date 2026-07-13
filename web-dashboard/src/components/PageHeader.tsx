import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Optional controls rendered on the right (e.g. AutoRefreshControl, selects). */
  actions?: ReactNode;
  className?: string;
}

/**
 * Standard page header: a title, an optional muted description (hidden on
 * small screens, matching the existing pages), and an optional actions slot.
 */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4",
        className,
      )}
    >
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h2>
        {description && (
          <p className="text-muted-foreground mt-1 sm:mt-2 text-sm sm:text-base hidden sm:block">
            {description}
          </p>
        )}
      </div>
      {actions}
    </div>
  );
}
