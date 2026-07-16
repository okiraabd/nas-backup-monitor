export const DASHBOARD_ACCESS_MESSAGE =
  "This account cannot access the dashboard. Only admin and operator accounts are allowed.";

export function isDashboardRole(role: string | null | undefined) {
  return role === "admin" || role === "operator";
}

export class DashboardAccessError extends Error {
  constructor() {
    super(DASHBOARD_ACCESS_MESSAGE);
    this.name = "DashboardAccessError";
  }
}
