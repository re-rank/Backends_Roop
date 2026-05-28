"use client";

import { Building2, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/stores/auth-store";

export function Header() {
  const { user, logout, organization, organizations, setOrganization } =
    useAuthStore();

  return (
    <header className="flex h-14 items-center gap-2 border-b px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-6" />

      {/* 조직 선택기 */}
      {organizations.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="outline" size="sm" className="gap-2" />}
          >
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">
              {organization?.name ?? "조직 선택"}
            </span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {organizations.map((org) => (
              <DropdownMenuItem
                key={org.id}
                onClick={() => setOrganization(org)}
                className={
                  org.id === organization?.id ? "bg-accent" : undefined
                }
              >
                {org.name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <div className="flex-1" />

      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" size="sm" className="gap-2" />}
        >
          <User className="h-4 w-4" />
          <span className="hidden sm:inline">{user?.name ?? "사용자"}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <div className="px-2 py-1.5 text-sm text-muted-foreground">
            {user?.email}
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            로그아웃
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
