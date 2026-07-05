import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { BackupLogs } from "./pages/BackupLogs";
import { BackupLogDetail } from "./pages/BackupLogDetail";
import { MonitorNas } from "./pages/MonitorNas";
import { MonitorCeph } from "./pages/MonitorCeph";
import { Reports } from "./pages/Reports";
import { CollectorStatus } from "./pages/CollectorStatus";
import { Users } from "./pages/Users";

const NotFound = () => <div className="p-10 text-xl font-bold text-destructive">404 - Not Found</div>;

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Protected Routes */}
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="logs" element={<BackupLogs />} />
          <Route path="logs/:id" element={<BackupLogDetail />} />
          <Route path="monitor/nas" element={<MonitorNas />} />
          <Route path="monitor/ceph" element={<MonitorCeph />} />
          <Route path="monitor/collector" element={<CollectorStatus />} />
          <Route path="reports" element={<Reports />} />
          
          <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
            <Route path="users" element={<Users />} />
          </Route>
          
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default App;
