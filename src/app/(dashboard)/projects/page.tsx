"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import type { Organization, Project } from "@/types/api";

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("");

  const { data: orgs } = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: Organization[] }>(
        "/api/v1/organizations",
      );
      return data.data;
    },
  });

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: Project[] }>(
        "/api/v1/projects",
      );
      return data.data;
    },
  });

  const createProject = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post("/api/v1/projects", {
        organization_id: selectedOrg,
        name,
        description: description || undefined,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("프로젝트가 생성되었습니다.");
      setOpen(false);
      setName("");
      setDescription("");
      setSelectedOrg("");
    },
    onError: () => {
      toast.error("프로젝트 생성에 실패했습니다.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg) {
      toast.error("조직을 선택해주세요.");
      return;
    }
    createProject.mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">보호 현황</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="mr-2 h-4 w-4" />
            프로젝트 생성
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>새 프로젝트 생성</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>조직 *</Label>
                <Select value={selectedOrg} onValueChange={(v) => setSelectedOrg(v ?? "")}>
                  <SelectTrigger>
                    <SelectValue placeholder="조직 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    {orgs?.map((org) => (
                      <SelectItem key={org.id} value={org.id}>
                        {org.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="projectName">프로젝트명 *</Label>
                <Input
                  id="projectName"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="예: 2026 SS 컬렉션"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="projectDesc">설명</Label>
                <Input
                  id="projectDesc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="프로젝트 설명 (선택)"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={createProject.isPending}
              >
                {createProject.isPending ? "생성 중..." : "생성"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      ) : projects && projects.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}`}>
              <Card className="transition-shadow hover:shadow-md">
                <CardHeader className="flex flex-row items-center gap-3">
                  <FolderOpen className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-lg">{project.name}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                  {project.description && <p>{project.description}</p>}
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{project.status}</Badge>
                    <span>
                      {new Date(project.created_at).toLocaleDateString("ko-KR")}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            아직 등록된 프로젝트가 없습니다. 먼저 조직을 생성한 후 프로젝트를
            추가해주세요.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
