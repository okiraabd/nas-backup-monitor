import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import {
  DashboardAccessError,
  isDashboardRole,
} from "./dashboard-access";
import type { User } from "./types";

export type { User };

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      // Verify token is still valid
      api.get("/auth/me")
        .then((res) => {
          if (!isDashboardRole(res.data.role)) {
            localStorage.removeItem("token");
            setUser(null);
            window.location.replace("/login?accessDenied=1");
            return;
          }
          setUser(res.data);
        })
        .catch(() => {
          localStorage.removeItem("token");
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = (token: string, userData: User) => {
    if (!isDashboardRole(userData.role)) {
      localStorage.removeItem("token");
      setUser(null);
      throw new DashboardAccessError();
    }
    localStorage.setItem("token", token);
    setUser(userData);
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      console.error("Logout failed or token already revoked", e);
    } finally {
      localStorage.removeItem("token");
      setUser(null);
      window.location.href = "/login";
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
