// 患者类型
export interface Patient {
  id: string
  name: string
  gender: 'M' | 'F' | string
  age: number
  phone: string
  medical_history?: string
  allergies?: string
  family_history?: string
  created_at: string
  updated_at: string
}

export interface PatientCreate {
  name: string
  gender: string
  age: number
  phone: string
  medical_history?: string
  allergies?: string
  family_history?: string
}

export interface PatientReport {
  id: string
  patient_id: string
  file_name: string
  file_path: string
  content_type?: string
  file_size?: number
  uploaded_at: string
  download_url: string
}

// 息肉类型
export interface PolypInfo {
  number: number
  bbox: { x: number; y: number; width: number; height: number }
  area: number
  diameter_mm: number
  boundary_score: number
  shape_type: 'pedunculated' | 'sessile' | 'flat'
  confidence: number
  location?: string
  pathology_pred?: string
}

// LLM分析结果
export interface LLMAnalysis {
  risk_level: 'low' | 'medium' | 'high'
  pathology_type: string
  recommended_followup_days: number
  treatment_recommendation?: string
  key_findings?: string[]
  risk_factors?: string[]
  doctor_explanation: string
  patient_explanation: string
  treatment_suggestions: string[]
  dietary_advice: string[]
  followup_plan: string
  clinical_report?: string
  historical_comparison?: string
  progression_assessment?: string
  llm_model_key?: string
  llm_model_id?: string
  llm_model_label?: string
}

export interface LLMModelOption {
  key: string
  label: string
  provider: string
  available: boolean
  default: boolean
}

export interface DoctorConfirmedReport {
  risk_level: string
  pathology_type: string
  treatment_recommendation: string
  followup_plan: string
  clinical_report: string
  historical_comparison?: string
  progression_assessment?: string
}

// 检查记录类型
export interface Examination {
  id: string
  patient_id: string
  exam_date: string
  exam_type: string
  image_path?: string
  result_path?: string
  report_path?: string
  polyp_count: number
  risk_level?: string
  pathology_type?: string
  recommended_followup?: number
  llm_analysis?: LLMAnalysis
  llm_model_key?: string
  llm_model_id?: string
  doctor_notes?: string
  doctor_confirmed_report?: DoctorConfirmedReport
  doctor_reviewed?: boolean
  doctor_reviewed_at?: string
  created_at: string
  polyps?: PolypInfo[]
}

export interface ExaminationList {
  id: string
  patient_id: string
  exam_date: string
  exam_type: string
  polyp_count: number
  risk_level?: string
  created_at: string
}

// 随访计划
export interface FollowupPlan {
  id: string
  patient_id: string
  examination_id: string
  next_exam_date: string
  status: 'pending' | 'completed' | 'overdue'
  reminder_sent: boolean
  notes?: string
  created_at: string
}

// API响应通用
export interface ApiResponse<T> {
  data: T
  message?: string
  success?: boolean
}

// 风险等级映射
export const RISK_LEVEL_MAP: Record<string, { label: string; color: string }> = {
  low: { label: '低风险', color: 'green' },
  medium: { label: '中风险', color: 'orange' },
  high: { label: '高风险', color: 'red' },
  pending: { label: '待分析', color: 'blue' },
}

// 形态类型映射
export const SHAPE_TYPE_MAP: Record<string, string> = {
  pedunculated: '有蒂型',
  sessile: '无蒂型',
  flat: '扁平型',
}

// 统计数据
export interface DashboardStats {
  total_patients: number
  total_examinations: number
  pending_followups: number
  high_risk_cases: number
}
