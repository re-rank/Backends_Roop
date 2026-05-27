// ========== 공통 ==========
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ========== User ==========
export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  plan_type: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ========== Organization ==========
export interface Organization {
  id: string;
  owner_id: string;
  name: string;
  brand_name: string | null;
  business_number: string | null;
  contact_email: string | null;
  created_at: string;
  updated_at: string;
}

// ========== Project ==========
export interface Project {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ========== Image ==========
export interface OriginalImage {
  id: string;
  project_id: string;
  image_id: string;
  original_filename: string | null;
  file_size_bytes: number | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  sha256_hash: string;
  product_name: string | null;
  brand_name: string | null;
  shot_date: string | null;
  rights_holder: string | null;
  status: string;
  registered_at: string;
  created_at: string;
}

// ========== Detection ==========
export interface DetectionRequest {
  id: string;
  organization_id: string;
  request_type: string;
  suspect_url: string | null;
  status: string;
  result_summary: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
}

export interface DetectedMatch {
  id: string;
  detection_request_id: string;
  original_image_id: string | null;
  watermark_detected: boolean;
  similarity_phash: number | null;
  similarity_clip: number | null;
  similarity_dino: number | null;
  overall_score: number | null;
  transformation_types: string[] | null;
  risk_level: string | null;
  created_at: string;
}

// ========== Case ==========
export interface InfringementCase {
  id: string;
  organization_id: string;
  detected_match_id: string | null;
  case_number: string;
  title: string | null;
  status: string;
  suspect_url: string | null;
  suspect_seller_name: string | null;
  suspect_platform: string | null;
  overall_score: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceFile {
  id: string;
  infringement_case_id: string;
  file_type: string;
  file_storage_key: string;
  file_name: string | null;
  sha256_hash: string | null;
  captured_at: string | null;
  created_at: string;
}

// ========== Dashboard ==========
export interface DashboardStats {
  total_images: number;
  protected_images: number;
  open_cases: number;
  total_detections: number;
}
