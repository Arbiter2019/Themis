import type { Experiment, LabelingExperiment, LabelingTask, LabelingTaskDetail, Report } from "../types";

const API_BASE = "";

export interface Session {
  token: string;
  username: string;
  role: "admin" | "labeler";
}

let session: Session | null = (() => {
  const raw = localStorage.getItem("themis_session");
  return raw ? JSON.parse(raw) : null;
})();

export function getSession() {
  return session;
}

export function saveSession(next: Session | null) {
  session = next;
  if (next) localStorage.setItem("themis_session", JSON.stringify(next));
  else localStorage.removeItem("themis_session");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (session?.token) headers.set("Authorization", `Bearer ${session.token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<Session>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  listExperiments: () => request<Experiment[]>("/api/experiments"),
  getExperiment: (id: number) => request<Experiment>(`/api/experiments/${id}`),
  createExperiment: (payload: unknown) => request<Experiment>("/api/experiments", { method: "POST", body: JSON.stringify(payload) }),
  updateExperiment: (id: number, payload: unknown) =>
    request<Experiment>(`/api/experiments/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  importSamples: (id: number, samples: unknown[]) =>
    request<{ imported: number; errors: unknown[] }>(`/api/experiments/${id}/import`, {
      method: "POST",
      body: JSON.stringify({ samples })
    }),
  report: (id: number) => request<Report>(`/api/experiments/${id}/report`),
  closeExperiment: (id: number) => request<Experiment>(`/api/experiments/${id}/close`, { method: "POST", body: "{}" }),
  labelingExperiments: () => request<LabelingExperiment[]>("/api/labeling/experiments"),
  labelingTasks: (experimentId: number) => request<LabelingTask[]>(`/api/labeling/experiments/${experimentId}/tasks`),
  labelingTask: (taskId: number) => request<LabelingTaskDetail>(`/api/labeling/tasks/${taskId}`),
  submitLabel: (taskId: number, selected_variant_id: number) =>
    request<{ ok: true }>(`/api/labeling/tasks/${taskId}/submit`, {
      method: "POST",
      body: JSON.stringify({ selected_variant_id })
    })
};
