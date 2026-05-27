"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FolderOpen,
  Home,
  ImageIcon,
  Scale,
  Search,
  Settings,
  Shield,
  Upload,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const mainNav = [
  { title: "대시보드", href: "/dashboard", icon: Home },
  { title: "조직 관리", href: "/organizations", icon: FolderOpen },
];

const protectionNav = [
  { title: "이미지 업로드", href: "/protection/upload", icon: Upload },
  { title: "보호 현황", href: "/projects", icon: Shield },
];

const analysisNav = [
  { title: "도용 분석", href: "/detection", icon: Search },
  { title: "침해 사건", href: "/cases", icon: Scale },
  { title: "스크리닝", href: "/screening", icon: BarChart3 },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <Link href="/dashboard" className="flex items-center gap-2">
          <ImageIcon className="h-6 w-6 text-primary" />
          <span className="text-lg font-bold">Re-Proof</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <NavGroup label="메인" items={mainNav} pathname={pathname} />
        <NavGroup label="이미지 보호" items={protectionNav} pathname={pathname} />
        <NavGroup label="도용 탐지" items={analysisNav} pathname={pathname} />

        <SidebarGroup className="mt-auto">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/settings" />}
                  isActive={pathname === "/settings"}
                >
                  <Settings className="h-4 w-4" />
                  <span>설정</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}

function NavGroup({
  label,
  items,
  pathname,
}: {
  label: string;
  items: { title: string; href: string; icon: React.ComponentType<{ className?: string }> }[];
  pathname: string;
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.href}>
              <SidebarMenuButton
                render={<Link href={item.href} />}
                isActive={pathname.startsWith(item.href)}
              >
                <item.icon className="h-4 w-4" />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
