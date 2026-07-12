import { NavLink } from "react-router-dom";
import { LayoutDashboard, History, Activity, Database, FileText, Users, Server, X } from "lucide-react";
import { cn } from "@/lib/utils";

const navGroups = [
  {
    title: "MAIN",
    items: [
      { title: "Overview", href: "/dashboard", icon: LayoutDashboard },
      { title: "Backup Logs", href: "/dashboard/logs", icon: History },
    ]
  },
  {
    title: "MONITORING",
    items: [
      { title: "NAS", href: "/dashboard/monitor/nas", icon: Server },
      { title: "Ceph Storage", href: "/dashboard/monitor/ceph", icon: Database },
      { title: "Collector Status", href: "/dashboard/monitor/collector", icon: Activity },
    ]
  },
  {
    title: "ADMINISTRATION",
    items: [
      { title: "Reports", href: "/dashboard/reports", icon: FileText },
      { title: "Users", href: "/dashboard/users", icon: Users, adminOnly: true },
    ]
  }
];

interface SidebarProps {
  userRole: string;
  isOpen: boolean;
  onClose: () => void;
  onNavigate: () => void;
}

export function Sidebar({ userRole, isOpen, onClose, onNavigate }: SidebarProps) {
  return (
    <>
      {/* Mobile backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          // Base styles
          "flex h-full w-64 flex-col border-r bg-card text-card-foreground",
          // Mobile: fixed overlay, slide from left
          "fixed inset-y-0 left-0 z-50 transition-transform duration-300 ease-in-out",
          "md:relative md:translate-x-0 md:transition-none md:z-auto",
          // Mobile visibility
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header with close button for mobile */}
        <div className="p-6 pb-2 flex items-center justify-between">
          <h2 className="text-xl font-bold tracking-tight text-primary">Backup Monitor</h2>
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded-md hover:bg-muted text-muted-foreground"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
          {navGroups.map((group, i) => {
            // Filter items based on role
            const visibleItems = group.items.filter(item => !(item.adminOnly && userRole !== "admin"));
            
            if (visibleItems.length === 0) return null;

            return (
              <div key={i} className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-3">
                  {group.title}
                </h4>
                <nav className="space-y-1">
                  {visibleItems.map((item) => (
                    <NavLink
                      key={item.href}
                      to={item.href}
                      end={item.href === "/dashboard"}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-primary text-primary-foreground shadow-sm"
                            : "hover:bg-muted hover:text-foreground text-muted-foreground"
                        )
                      }
                    >
                      <item.icon className="h-4 w-4" />
                      {item.title}
                    </NavLink>
                  ))}
                </nav>
              </div>
            );
          })}
        </div>
        <div className="p-4 border-t text-xs text-muted-foreground text-center bg-muted/20">
          NAS Backup System v1.0
        </div>
      </div>
    </>
  );
}
