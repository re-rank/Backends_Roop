"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, X, ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import type { PaginatedResponse, Project } from "@/types/api";

interface FileWithPreview extends File {
  preview?: string;
}

export default function UploadPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [selectedProject, setSelectedProject] = useState(
    searchParams.get("project") ?? "",
  );
  const [files, setFiles] = useState<FileWithPreview[]>([]);

  const { organization } = useAuthStore();

  const { data: projects } = useQuery({
    queryKey: ["projects", organization?.id],
    queryFn: async () => {
      if (!organization) return [];
      const { data } = await apiClient.get<PaginatedResponse<Project>>(
        `/api/v1/organizations/${organization.id}/projects`,
      );
      return data.items;
    },
    enabled: !!organization,
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const withPreview = acceptedFiles.map((f) =>
      Object.assign(f, { preview: URL.createObjectURL(f) }),
    );
    setFiles((prev) => [...prev, ...withPreview]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".png", ".jpg", ".jpeg", ".webp", ".tiff"] },
    maxSize: 20 * 1024 * 1024,
  });

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const copy = [...prev];
      if (copy[index].preview) URL.revokeObjectURL(copy[index].preview!);
      copy.splice(index, 1);
      return copy;
    });
  };

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const results = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const { data } = await apiClient.post(
          `/api/v1/projects/${selectedProject}/images`,
          formData,
          { headers: { "Content-Type": "multipart/form-data" } },
        );
        results.push(data);
      }
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", selectedProject, "images"] });
      toast.success(`${files.length}개 이미지가 업로드되었습니다.`);
      files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview));
      setFiles([]);
    },
    onError: () => {
      toast.error("이미지 업로드에 실패했습니다.");
    },
  });

  const handleUpload = () => {
    if (!selectedProject) {
      toast.error("프로젝트를 선택해주세요.");
      return;
    }
    if (files.length === 0) {
      toast.error("업로드할 이미지를 선택해주세요.");
      return;
    }
    uploadMutation.mutate();
  };

  const progress = uploadMutation.isPending ? 50 : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">이미지 업로드</h1>

      {/* Project Selection */}
      <div className="max-w-sm space-y-2">
        <Label>프로젝트 선택 *</Label>
        <Select value={selectedProject} onValueChange={(v) => setSelectedProject(v ?? "")}>
          <SelectTrigger>
            <SelectValue placeholder="프로젝트 선택" />
          </SelectTrigger>
          <SelectContent>
            {projects?.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Dropzone */}
      <Card>
        <CardHeader>
          <CardTitle>파일 선택</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              이미지를 드래그하거나 클릭하여 선택하세요
            </p>
            <p className="text-xs text-muted-foreground">
              PNG, JPG, WEBP, TIFF (최대 20MB)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* File List */}
      {files.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>선택된 파일 ({files.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {files.map((file, i) => (
              <div
                key={`${file.name}-${i}`}
                className="flex items-center gap-3 rounded border p-2"
              >
                {file.preview ? (
                  <img
                    src={file.preview}
                    alt={file.name}
                    className="h-10 w-10 rounded object-cover"
                  />
                ) : (
                  <ImageIcon className="h-10 w-10 text-muted-foreground" />
                )}
                <div className="flex-1 truncate">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeFile(i)}
                  disabled={uploadMutation.isPending}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}

            {uploadMutation.isPending && (
              <Progress value={progress} className="mt-2" />
            )}

            <Button
              onClick={handleUpload}
              className="mt-4 w-full"
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending
                ? "업로드 중..."
                : `${files.length}개 이미지 업로드`}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
