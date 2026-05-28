"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ImageIcon } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (user) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-8">
      <div className="w-full max-w-[26rem] space-y-8">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ImageIcon className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Re-Proof</h1>
          <p className="text-sm text-muted-foreground">
            AI 변형 이미지 도용 추적 및 원본 증명 플랫폼
          </p>
        </div>
        {children}
      </div>
    </div>
  );
}
