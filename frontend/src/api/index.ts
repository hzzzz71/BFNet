import api from './client'
import axios from 'axios'
import type { Patient, PatientCreate, PatientReport, Examination, ExaminationList, DashboardStats, DoctorConfirmedReport, LLMModelOption } from '../types'

// ────────────────────────────────────────────
// 患者 API
// ────────────────────────────────────────────
export const patientApi = {
  list: (params?: { skip?: number; limit?: number; name?: string }) =>
    api.get<Patient[]>('/patients/', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Patient>(`/patients/${id}`).then(r => r.data),

  create: (data: PatientCreate) =>
    api.post<Patient>('/patients/', data).then(r => r.data),

  update: (id: string, data: Partial<PatientCreate>) =>
    api.put<Patient>(`/patients/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/patients/${id}`),

  listReports: (id: string) =>
    api.get<PatientReport[]>(`/patients/${id}/reports`).then(r => r.data),

  uploadReport: (id: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<PatientReport>(
      `/patients/${id}/reports`,
      fd,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      }
    ).then(r => r.data)
  },

  deleteReport: (id: string, reportId: string) =>
    api.delete(`/patients/${id}/reports/${reportId}`),
}

// ────────────────────────────────────────────
// 检查 API
// ────────────────────────────────────────────
export const examinationApi = {
  list: (params?: { patient_id?: string; skip?: number; limit?: number }) =>
    api.get<ExaminationList[]>('/examinations/', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Examination>(`/examinations/${id}`).then(r => r.data),

  upload: (patientId: string, file: File, clinicalNotes?: string, llmModelKey?: string, onProgress?: (p: number) => void) => {
    const fd = new FormData()
    fd.append('file', file)
    if (clinicalNotes?.trim()) {
      fd.append('clinical_notes', clinicalNotes.trim())
    }
    if (llmModelKey?.trim()) {
      fd.append('llm_model_key', llmModelKey.trim())
    }
    return api.post<Examination>(
      `/examinations/upload?patient_id=${patientId}`,
      fd,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
        onUploadProgress: e => onProgress && e.total && onProgress(Math.round(e.loaded * 100 / e.total)),
      }
    ).then(r => r.data)
  },

  delete: (id: string) =>
    api.delete(`/examinations/${id}`),
}

// ────────────────────────────────────────────
// LLM 分析 API
// ────────────────────────────────────────────
export const analysisApi = {
  getModels: () =>
    api.get<LLMModelOption[]>('/analysis/models').then(r => r.data),

  analyze: (examinationId: string, llmModelKey?: string) =>
    api.post(
      `/analysis/analyze/${examinationId}`,
      llmModelKey ? { llm_model_key: llmModelKey } : {},
      { timeout: 300000 }
    ).then(r => r.data),

  getReport: (examinationId: string) =>
    api.get(`/analysis/report/${examinationId}`).then(r => r.data),

  saveDoctorReview: (examinationId: string, payload: DoctorConfirmedReport) =>
    api.put(`/analysis/report/${examinationId}/doctor-review`, payload).then(r => r.data),

  downloadConfirmedReport: (examinationId: string) =>
    api.get(`/analysis/report/${examinationId}/download`, { responseType: 'blob' }).then(r => r.data),
}

// ────────────────────────────────────────────
// 系统 API
// ────────────────────────────────────────────
export const systemApi = {
  health: () =>
    axios.get(`${window.location.protocol}//${window.location.hostname}:8000/health`)
      .then(r => r.data)
      .catch(() => ({ status: 'error', model: 'unknown', database: 'unknown' })),

  stats: async (): Promise<DashboardStats> => {
    // 聚合统计
    const [patients, examinations] = await Promise.all([
      patientApi.list({ limit: 1000 }),
      examinationApi.list({ limit: 1000 }),
    ])
    const highRisk = examinations.filter(e => e.risk_level === 'high').length
    return {
      total_patients: patients.length,
      total_examinations: examinations.length,
      pending_followups: examinations.filter(e => !e.risk_level || e.risk_level === 'pending').length,
      high_risk_cases: highRisk,
    }
  }
}
