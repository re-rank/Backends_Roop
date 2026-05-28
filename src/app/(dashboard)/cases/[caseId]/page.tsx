"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/lib/api-client";
import type { InfringementCase, EvidenceFile } from "@/types/api";

export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);

  const { data: caseData, isLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<InfringementCase>(
        `/api/v1/cases/${caseId}`,
      );
      return data;
    },
  });

  const { data: evidence } = useQuery({
    queryKey: ["case", caseId, "evidence"],
    queryFn: async () => {
      const { data } = await apiClient.get<EvidenceFile[]>(
        `/api/v1/cases/${caseId}/evidence`,
      );
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        사건을 찾을 수 없습니다.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/cases">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">
            {caseData.title ?? caseData.case_number}
          </h1>
          <p className="text-sm text-muted-foreground">
            사건번호: {caseData.case_number}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Case Info */}
        <Card>
          <CardHeader>
            <CardTitle>사건 정보</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <InfoRow label="상태" value={<Badge variant="outline">{caseData.status}</Badge>} />
            <InfoRow label="의심 URL" value={caseData.suspect_url ?? "-"} />
            <InfoRow label="판매자" value={caseData.suspect_seller_name ?? "-"} />
            <InfoRow label="플랫폼" value={caseData.suspect_platform ?? "-"} />
            <InfoRow
              label="유사도"
              value={
                caseData.overall_score != null
                  ? `${(caseData.overall_score * 100).toFixed(1)}%`
                  : "-"
              }
            />
            <InfoRow
              label="등록일"
              value={new Date(caseData.created_at).toLocaleString("ko-KR")}
            />
            {caseData.notes && <InfoRow label="메모" value={caseData.notes} />}
          </CardContent>
        </Card>

        {/* Evidence */}
        <Card>
          <CardHeader>
            <CardTitle>증거 파일</CardTitle>
          </CardHeader>
          <CardContent>
            {evidence && evidence.length > 0 ? (
              <div className="space-y-2">
                {evidence.map((e) => (
                  <div
                    key={e.id}
                    className="flex items-center justify-between rounded border p-2 text-sm"
                  >
                    <span>{e.file_name ?? e.file_type}</span>
                    <span className="text-xs text-muted-foreground">
                      {e.captured_at
                        ? new Date(e.captured_at).toLocaleDateString("ko-KR")
                        : "-"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                등록된 증거 파일이 없습니다.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="w-20 shrink-0 text-muted-foreground">{label}</span>
      <span className="break-all">{value}</span>
    </div>
  );
}
