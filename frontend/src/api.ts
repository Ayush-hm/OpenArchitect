import type { WorkflowRunResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function uploadArchitectureDocument(file: File): Promise<WorkflowRunResponse> {
  const form = new FormData();
  form.append("file", file);

  const response = await fetch(`${API_BASE_URL}/workflows/architecture-review/upload`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail = errorBody?.detail ?? `Request failed with HTTP ${response.status}`;
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchHealth(): Promise<{ status: string; engine: string }> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }
  return response.json();
}
