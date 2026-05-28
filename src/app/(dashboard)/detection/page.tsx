"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import type { DetectionRequest } from "@/types/api";

export default function DetectionPage() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<DetectionRequest | null>(null);
  const { organization } = useAuthStore();

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      if (!organization) throw new Error("조직을 먼저 선택해주세요.");
      const { data } = await apiClient.post<DetectionRequest>(
        `/api/v1/detection/analyze-url?organization_id=${organization.id}`,
        { suspect_url: url },
      );
      return data;
    },
    onSuccess: (data) => {
      setResult(data);
      toast.success("분석 요청이 등록되었습니다.");
    },
    onError: () => {
      toast.error("분석 요청에 실패했습니다.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!organization) {
      toast.error("조직을 먼저 선택해주세요.");
      return;
    }
    if (!url.trim()) {
      toast.error("URL을 입력해주세요.");
      return;
    }
    analyzeMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">도용 분석</h1>

      <Card>
        <CardHeader>
          <CardTitle>URL로 분석</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="suspectUrl">의심 URL</Label>
              <Input
                id="suspectUrl"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/product-image.jpg"
                required
              />
            </div>
            <Button type="submit" disabled={analyzeMutation.isPending}>
              <Search className="mr-2 h-4 w-4" />
              {analyzeMutation.isPending ? "분석 중..." : "분석 시작"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>분석 결과</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">상태:</span>
              <Badge variant="outline">{result.status}</Badge>
            </div>
            <div>
              <span className="text-muted-foreground">요청 ID:</span>{" "}
              <code className="text-xs">{result.id}</code>
            </div>
            <div>
              <span className="text-muted-foreground">요청일:</span>{" "}
              {new Date(result.created_at).toLocaleString("ko-KR")}
            </div>
            <p className="text-muted-foreground">
              비동기 분석이 진행됩니다. 결과는 침해 사건 페이지에서 확인할 수 있습니다.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
