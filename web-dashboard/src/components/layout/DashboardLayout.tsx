import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useAuth } from "@/lib/auth";

export function DashboardLayout() {
  const { user } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar userRole={user?.role || "service"} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 bg-muted/20">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
