import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const Projects = {
  list: () => api.get("/projects").then((r) => r.data),
  create: (payload) => api.post("/projects", payload).then((r) => r.data),
  get: (id) => api.get(`/projects/${id}`).then((r) => r.data),
  update: (id, payload) => api.put(`/projects/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/projects/${id}`).then((r) => r.data),
  rewrite: (id) => api.post(`/projects/${id}/rewrite`).then((r) => r.data),
  splitScenes: (id) => api.post(`/projects/${id}/split-scenes`).then((r) => r.data),
  export: (id) => api.get(`/projects/${id}/export`).then((r) => r.data),
  costEstimate: (id) => api.get(`/projects/${id}/cost-estimate`).then((r) => r.data),
  sceneCosts: (id) => api.get(`/projects/${id}/scene-costs`).then((r) => r.data),
};

export const Characters = {
  create: (projectId, payload) =>
    api.post(`/projects/${projectId}/characters`, payload).then((r) => r.data),
  update: (id, payload) => api.put(`/characters/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/characters/${id}`).then((r) => r.data),
};

export const Scenes = {
  create: (projectId, payload) =>
    api.post(`/projects/${projectId}/scenes`, payload).then((r) => r.data),
  update: (id, payload) => api.put(`/scenes/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/scenes/${id}`).then((r) => r.data),
  generateImage: (id) => api.post(`/scenes/${id}/generate-image`).then((r) => r.data),
  generateSegment: (id) => api.post(`/scenes/${id}/segments`).then((r) => r.data),
  expand: (id) => api.post(`/scenes/${id}/expand`).then((r) => r.data),
  reduceToDraft: (id) => api.post(`/scenes/${id}/reduce-to-draft`).then((r) => r.data),
  reorder: (projectId, sceneIds) =>
    api
      .put(`/projects/${projectId}/scenes/reorder`, { scene_ids: sceneIds })
      .then((r) => r.data),
  reorderSegments: (sceneId, segmentIds) =>
    api
      .put(`/scenes/${sceneId}/segments/reorder`, { segment_ids: segmentIds })
      .then((r) => r.data),
};

export const Segments = {
  setStatus: (id, status) =>
    api.put(`/segments/${id}/status`, { status }).then((r) => r.data),
  update: (id, payload) =>
    api.put(`/segments/${id}`, payload).then((r) => r.data),
  regenerate: (id) => api.post(`/segments/${id}/regenerate`).then((r) => r.data),
  remove: (id) => api.delete(`/segments/${id}`).then((r) => r.data),
};

export const Meta = {
  options: () => api.get("/meta/options").then((r) => r.data),
  me: () => api.get("/me").then((r) => r.data),
};

export const ProviderSettings = {
  options: () => api.get("/settings/providers/options").then((r) => r.data),
  get: () => api.get("/settings/providers").then((r) => r.data),
  update: (payload) => api.put("/settings/providers", payload).then((r) => r.data),
  test: (modality) =>
    api.post("/settings/providers/test", { modality }).then((r) => r.data),
};

export const FeatureFlags = {
  get: () => api.get("/feature-flags").then((r) => r.data),
};

export const ProjectProviders = {
  get: (projectId) =>
    api.get(`/projects/${projectId}/providers`).then((r) => r.data),
  update: (projectId, payload) =>
    api.put(`/projects/${projectId}/providers`, payload).then((r) => r.data),
  test: (projectId, modality) =>
    api
      .post(`/projects/${projectId}/providers/test`, { modality })
      .then((r) => r.data),
  voiceResolution: (projectId) =>
    api.get(`/projects/${projectId}/voice-resolution`).then((r) => r.data),
};

export const Admin = {
  stats: () => api.get("/admin/stats").then((r) => r.data),
  users: () => api.get("/admin/users").then((r) => r.data),
  projects: () => api.get("/admin/projects").then((r) => r.data),
  generations: () => api.get("/admin/generations").then((r) => r.data),
  failedJobs: () => api.get("/admin/failed-jobs").then((r) => r.data),
  providerActivity: (limit = 50) =>
    api.get(`/admin/provider-activity?limit=${limit}`).then((r) => r.data),
  providerHealth: (windowMinutes = 60) =>
    api.get(`/admin/provider-health?window_minutes=${windowMinutes}`).then((r) => r.data),
};
