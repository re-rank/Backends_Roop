"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">설정</h1>

      <Card>
        <CardHeader>
          <CardTitle>프로필 정보</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>이름</Label>
            <Input value={user?.name ?? ""} disabled />
          </div>
          <div className="space-y-2">
            <Label>이메일</Label>
            <Input value={user?.email ?? ""} disabled />
          </div>
          <div className="space-y-2">
            <Label>플랜</Label>
            <Input value={user?.plan_type ?? "free"} disabled />
          </div>
          <p className="text-sm text-muted-foreground">
            프로필 수정 기능은 준비 중입니다.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API 키 관리</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            외부 서비스 연동을 위한 API 키 관리 기능이 제공될 예정입니다.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
