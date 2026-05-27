"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

export default function ScreeningPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">스크리닝</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            대량 스크리닝
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            대량 이미지 스크리닝 기능은 준비 중입니다. 특정 플랫폼의 상품 목록을
            자동 수집하여 도용 여부를 일괄 분석하는 기능이 제공될 예정입니다.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
