"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { InfringementCase, PaginatedResponse } from "@/types/api";

const statusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  open: { label: "진행 중", variant: "default" },
  investigating: { label: "조사 중", variant: "secondary" },
  resolved: { label: "해결", variant: "outline" },
  closed: { label: "종료", variant: "outline" },
};

export default function CasesPage() {
  const { organization } = useAuthStore();

  const { data: cases, isLoading } = useQuery({
    queryKey: ["cases", organization?.id],
    queryFn: async () => {
      if (!organization) return [];
      const { data } = await apiClient.get<PaginatedResponse<InfringementCase>>(
        `/api/v1/organizations/${organization.id}/cases`,
      );
      return data.items;
    },
    enabled: !!organization,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">침해 사건</h1>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-3 p-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : cases && cases.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>사건번호</TableHead>
                  <TableHead>제목</TableHead>
                  <TableHead>플랫폼</TableHead>
                  <TableHead>유사도</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>등록일</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cases.map((c) => {
                  const info = statusMap[c.status] ?? {
                    label: c.status,
                    variant: "outline" as const,
                  };
                  return (
                    <TableRow key={c.id}>
                      <TableCell>
                        <Link
                          href={`/cases/${c.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {c.case_number}
                        </Link>
                      </TableCell>
                      <TableCell>{c.title ?? "-"}</TableCell>
                      <TableCell>{c.suspect_platform ?? "-"}</TableCell>
                      <TableCell>
                        {c.overall_score != null
                          ? `${(c.overall_score * 100).toFixed(0)}%`
                          : "-"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={info.variant}>{info.label}</Badge>
                      </TableCell>
                      <TableCell>
                        {new Date(c.created_at).toLocaleDateString("ko-KR")}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="py-12 text-center text-muted-foreground">
              아직 등록된 침해 사건이 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
