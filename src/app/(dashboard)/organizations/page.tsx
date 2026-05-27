"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import type { Organization } from "@/types/api";

export default function OrganizationsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [brandName, setBrandName] = useState("");

  const { data: orgs, isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: Organization[] }>(
        "/api/v1/organizations",
      );
      return data.data;
    },
  });

  const createOrg = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post("/api/v1/organizations", {
        name,
        brand_name: brandName || undefined,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      toast.success("조직이 생성되었습니다.");
      setOpen(false);
      setName("");
      setBrandName("");
    },
    onError: () => {
      toast.error("조직 생성에 실패했습니다.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createOrg.mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">조직 관리</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="mr-2 h-4 w-4" />
            조직 생성
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>새 조직 생성</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="orgName">조직명 *</Label>
                <Input
                  id="orgName"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="예: 우리 회사"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="brandName">브랜드명</Label>
                <Input
                  id="brandName"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  placeholder="예: Our Brand"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={createOrg.isPending}
              >
                {createOrg.isPending ? "생성 중..." : "생성"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : orgs && orgs.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {orgs.map((org) => (
            <OrgCard key={org.id} org={org} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            아직 등록된 조직이 없습니다. 새 조직을 생성해주세요.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function OrgCard({ org }: { org: Organization }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{org.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm text-muted-foreground">
        {org.brand_name && <p>브랜드: {org.brand_name}</p>}
        {org.contact_email && <p>연락처: {org.contact_email}</p>}
        <p>생성일: {new Date(org.created_at).toLocaleDateString("ko-KR")}</p>
      </CardContent>
    </Card>
  );
}
