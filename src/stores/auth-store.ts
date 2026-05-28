import { create } from "zustand";
import apiClient from "@/lib/api-client";
import type { Organization, PaginatedResponse, TokenResponse, User } from "@/types/api";

interface AuthState {
  user: User | null;
  organization: Organization | null;
  organizations: Organization[];
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setOrganization: (org: Organization | null) => void;

  signup: (email: string, password: string, name: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  fetchOrganizations: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  organization: null,
  organizations: [],
  isLoading: false,

  setUser: (user) => set({ user }),
  setOrganization: (org) => {
    set({ organization: org });
    if (typeof window !== "undefined") {
      if (org) {
        localStorage.setItem("selected_org_id", org.id);
      } else {
        localStorage.removeItem("selected_org_id");
      }
    }
  },

  signup: async (email, password, name) => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.post<TokenResponse>("/api/v1/auth/signup", {
        email,
        password,
        name,
      });
      localStorage.setItem("access_token", data.access_token);
      set({ user: data.user });
    } finally {
      set({ isLoading: false });
    }
  },

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.post<TokenResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      localStorage.setItem("access_token", data.access_token);
      set({ user: data.user });
    } finally {
      set({ isLoading: false });
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("selected_org_id");
    set({ user: null, organization: null, organizations: [] });
    window.location.href = "/login";
  },

  fetchMe: async () => {
    try {
      const { data } = await apiClient.get<User>("/api/v1/auth/me");
      set({ user: data });
    } catch {
      set({ user: null });
    }
  },

  fetchOrganizations: async () => {
    try {
      const { data } = await apiClient.get<PaginatedResponse<Organization>>(
        "/api/v1/organizations",
      );
      const orgs = data.items;
      set({ organizations: orgs });

      // 이전에 선택한 조직 복원 또는 첫 번째 조직 자동 선택
      const current = get().organization;
      if (!current && orgs.length > 0) {
        const savedId =
          typeof window !== "undefined"
            ? localStorage.getItem("selected_org_id")
            : null;
        const restored = savedId ? orgs.find((o) => o.id === savedId) : null;
        set({ organization: restored ?? orgs[0] });
      }
    } catch {
      set({ organizations: [] });
    }
  },
}));
