import Link from "next/link";
import { ImageIcon, Shield, Search, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b px-6">
        <div className="flex items-center gap-2">
          <ImageIcon className="h-6 w-6 text-primary" />
          <span className="text-lg font-bold">Re-Proof</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" render={<Link href="/login" />}>
            로그인
          </Button>
          <Button size="sm" render={<Link href="/signup" />}>
            회원가입
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="flex flex-1 flex-col items-center justify-center gap-6 px-4 text-center">
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          AI 변형 이미지 도용,
          <br />
          <span className="text-primary">Re-Proof</span>가 추적합니다
        </h1>
        <p className="max-w-lg text-lg text-muted-foreground">
          상품 사진의 원본을 증명하고, AI로 변형된 도용 이미지를 자동 탐지하여
          권리를 보호하세요.
        </p>
        <div className="flex gap-3">
          <Button size="lg" render={<Link href="/signup" />}>
            무료로 시작하기
          </Button>
          <Button size="lg" variant="outline" render={<Link href="/login" />}>
            로그인
          </Button>
        </div>
      </section>

      {/* Features */}
      <section className="border-t bg-muted/40 px-6 py-16">
        <div className="mx-auto grid max-w-4xl gap-8 sm:grid-cols-3">
          <FeatureCard
            icon={<Shield className="h-8 w-8 text-primary" />}
            title="이미지 보호"
            description="워터마크 삽입 및 C2PA 메타데이터로 원본을 증명합니다."
          />
          <FeatureCard
            icon={<Search className="h-8 w-8 text-primary" />}
            title="도용 탐지"
            description="pHash, CLIP, DINOv2 기반 유사도 분석으로 도용을 추적합니다."
          />
          <FeatureCard
            icon={<FileText className="h-8 w-8 text-primary" />}
            title="증거 리포트"
            description="법적 대응을 위한 침해 증거 리포트를 자동 생성합니다."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t px-6 py-6 text-center text-sm text-muted-foreground">
        &copy; 2026 Re-Proof. All rights reserved.
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      {icon}
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
