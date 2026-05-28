"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Upload, ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/lib/api-client";
import type { PaginatedResponse, Project, OriginalImage } from "@/types/api";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () => {
      const { data } = await apiClient.get<Project>(
        `/api/v1/projects/${projectId}`,
      );
      return data;
    },
  });

  const { data: images, isLoading: imagesLoading } = useQuery({
    queryKey: ["project", projectId, "images"],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<OriginalImage>>(
        `/api/v1/projects/${projectId}/images`,
      );
      return data.items;
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/projects">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          {projectLoading ? (
            <Skeleton className="h-8 w-48" />
          ) : (
            <>
              <h1 className="text-2xl font-bold">{project?.name}</h1>
              {project?.description && (
                <p className="text-sm text-muted-foreground">
                  {project.description}
                </p>
              )}
            </>
          )}
        </div>
        <Button size="sm" render={<Link href={`/protection/upload?project=${projectId}`} />}>
          <Upload className="mr-2 h-4 w-4" />
          이미지 업로드
        </Button>
      </div>

      {/* Image Grid */}
      {imagesLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square" />
          ))}
        </div>
      ) : images && images.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {images.map((img) => (
            <Card key={img.id}>
              <CardContent className="flex flex-col items-center gap-2 pt-6">
                <div className="flex h-32 w-full items-center justify-center rounded bg-muted">
                  <ImageIcon className="h-10 w-10 text-muted-foreground" />
                </div>
                <p className="w-full truncate text-sm font-medium">
                  {img.original_filename ?? "이름 없음"}
                </p>
                <div className="flex w-full items-center justify-between">
                  <Badge variant="outline">{img.status}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {img.file_size_bytes
                      ? `${(img.file_size_bytes / 1024 / 1024).toFixed(1)}MB`
                      : "-"}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            이 프로젝트에 등록된 이미지가 없습니다.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
