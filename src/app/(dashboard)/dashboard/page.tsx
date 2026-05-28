"use client";

import { useQuery } from "@tanstack/react-query";
import { ImageIcon, Shield, Search, Scale } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { DashboardStats, InfringementCase } from "@/types/api";

export default function DashboardPage() {
  const { organization } = useAuthStore();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard", "stats", organization?.id],
    queryFn: async () => {
      if (!organization) return undefined;
      const { data } = await apiClient.get<DashboardStats>(
        `/api/v1/organizations/${organization.id}/dashboard/stats`,
      );
      return data;
    },
    enabled: !!organization,
  });

  const { data: recentCases, isLoading: casesLoading } = useQuery({
    queryKey: ["dashboard", "recent-cases", organization?.id],
    queryFn: async () => {
      if (!organization) return [];
      const { data } = await apiClient.get<InfringementCase[]>(
        `/api/v1/organizations/${organization.id}/dashboard/recent-cases`,
      );
      return data;
    },
    enabled: !!organization,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">대시보드</h1>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="전체 이미지"
          value={stats?.total_images}
          icon={<ImageIcon className="h-5 w-5 text-muted-foreground" />}
          loading={statsLoading}
        />
        <StatCard
          title="보호된 이미지"
          value={stats?.protected_images}
          icon={<Shield className="h-5 w-5 text-muted-foreground" />}
          loading={statsLoading}
        />
        <StatCard
          title="탐지 요청"
          value={stats?.total_detections}
          icon={<Search className="h-5 w-5 text-muted-foreground" />}
          loading={statsLoading}
        />
        <StatCard
          title="진행 중 사건"
          value={stats?.open_cases}
          icon={<Scale className="h-5 w-5 text-muted-foreground" />}
          loading={statsLoading}
        />
      </div>

      {/* Recent Cases */}
      <Card>
        <CardHeader>
          <CardTitle>최근 침해 사건</CardTitle>
        </CardHeader>
        <CardContent>
          {casesLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : recentCases && recentCases.length > 0 ? (
            <div className="space-y-3">
              {recentCases.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium">
                      {c.title ?? c.case_number}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {c.suspect_platform ?? "플랫폼 미확인"} &middot;{" "}
                      {new Date(c.created_at).toLocaleDateString("ko-KR")}
                    </p>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              아직 등록된 사건이 없습니다.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  loading,
}: {
  title: string;
  value: number | undefined;
  icon: React.ReactNode;
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between pt-6">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          {loading ? (
            <Skeleton className="mt-1 h-8 w-16" />
          ) : (
            <p className="text-3xl font-bold">{value ?? 0}</p>
          )}
        </div>
        {icon}
      </CardContent>
    </Card>
  );
}

const statusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  open: { label: "진행 중", variant: "default" },
  investigating: { label: "조사 중", variant: "secondary" },
  resolved: { label: "해결", variant: "outline" },
  closed: { label: "종료", variant: "outline" },
};

function StatusBadge({ status }: { status: string }) {
  const info = statusMap[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={info.variant}>{info.label}</Badge>;
}
