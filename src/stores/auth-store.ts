import { create } from "zustand";
import apiClient from "@/lib/api-client";
import type { Organization, TokenResponse, User } from "@/types/api";

interface AuthState {
  user: User | null;
  organization: Organization | null;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setOrganization: (org: Organization | null) => void;

  signup: (email: string, password: string, name: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  organization: null,
  isLoading: false,

  setUser: (user) => set({ user }),
  setOrganization: (org) => set({ organization: org }),

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
    set({ user: null, organization: null });
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
}));
