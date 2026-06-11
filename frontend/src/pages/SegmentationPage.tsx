import { useState, useRef, useEffect } from 'react'
import {
  Card, Row, Col, Button, Select, Upload, Typography, Space,
  Steps, Alert, Spin, Tag, Descriptions, Divider, Empty, message, Input,
  Statistic, Progress, List
} from 'antd'
import {
  ExperimentOutlined, RobotOutlined,
  CheckCircleFilled, LoadingOutlined, CloudUploadOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload'
import { patientApi, examinationApi, analysisApi } from '../api'
import type { Patient, Examination, ExaminationList, LLMModelOption } from '../types'
import { RISK_LEVEL_MAP, SHAPE_TYPE_MAP } from '../types'

const { Title, Text, Paragraph } = Typography
const { Dragger } = Upload

type Step = 'select' | 'upload' | 'segmenting' | 'done' | 'error'
const RESULT_CACHE_KEY = 'segmentation:last_exam_id'
const RESULT_LOCAL_CACHE_KEY = 'segmentation:last_exam_id:persistent'
const POLL_INTERVAL_MS = 2500
const POLL_MAX_TIMES = 180

export default function SegmentationPage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [selectedPatient, setSelectedPatient] = useState<string>('')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [previewUrl, setPreviewUrl] = useState<string>('')
  const [step, setStep] = useState<Step>('select')
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<Examination | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [isPollingAnalysis, setIsPollingAnalysis] = useState(false)
  const [isManualAnalyzing, setIsManualAnalyzing] = useState(false)
  const [analysisSyncText, setAnalysisSyncText] = useState('')
  const [outpatientNotes, setOutpatientNotes] = useState('')
  const [symptomDescription, setSymptomDescription] = useState('')
  const [clinicalJudgment, setClinicalJudgment] = useState('')
  const [modelOptions, setModelOptions] = useState<LLMModelOption[]>([])
  const [selectedModelKey, setSelectedModelKey] = useState<string>('')
  const pollingTimerRef = useRef<number | null>(null)
  const pollingCountRef = useRef(0)
  const resultRef = useRef<Examination | null>(null)
  const analysisNotifiedRef = useRef(false)

  useEffect(() => {
    resultRef.current = result
  }, [result])

  const stopPolling = () => {
    if (pollingTimerRef.current !== null) {
      window.clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
    pollingCountRef.current = 0
    setIsPollingAnalysis(false)
    setAnalysisSyncText('')
  }

  const rememberExamId = (examId: string) => {
    window.sessionStorage.setItem(RESULT_CACHE_KEY, examId)
    window.localStorage.setItem(RESULT_LOCAL_CACHE_KEY, examId)
  }

  const clearRememberedExamId = () => {
    window.sessionStorage.removeItem(RESULT_CACHE_KEY)
    window.localStorage.removeItem(RESULT_LOCAL_CACHE_KEY)
  }

  const syncExamResult = async (examId: string) => {
    try {
      const latest = await examinationApi.get(examId)
      const hadAnalysis = Boolean(resultRef.current?.llm_analysis)
      setResult(latest)
      setSelectedPatient(latest.patient_id)
      rememberExamId(latest.id)
      if (latest.llm_analysis) {
        stopPolling()
        if (!hadAnalysis && !analysisNotifiedRef.current) {
          analysisNotifiedRef.current = true
          message.success('LLM分析已完成，结果已自动更新')
        }
        return
      }
      pollingCountRef.current += 1
      setAnalysisSyncText(`LLM分析生成中，已同步等待 ${Math.ceil(pollingCountRef.current * POLL_INTERVAL_MS / 1000)} 秒`)
      if (pollingCountRef.current >= POLL_MAX_TIMES) {
        stopPolling()
        message.warning('LLM分析耗时较长，已停止自动轮询，可稍后在检查记录或详情页继续查看')
      }
    } catch {
      pollingCountRef.current += 1
      if (pollingCountRef.current >= POLL_MAX_TIMES) {
        stopPolling()
      }
    }
  }

  const startPolling = (examId: string) => {
    stopPolling()
    pollingCountRef.current = 0
    setIsPollingAnalysis(true)
    setAnalysisSyncText('BFNet分割已完成，正在同步等待LLM分析结果')
    rememberExamId(examId)
    void syncExamResult(examId)
    pollingTimerRef.current = window.setInterval(() => {
      void syncExamResult(examId)
    }, POLL_INTERVAL_MS)
  }

  useEffect(() => {
    patientApi.list({ limit: 200 }).then(setPatients)
    analysisApi.getModels().then((models) => {
      setModelOptions(models)
      const defaultModel = models.find((item) => item.default && item.available) || models.find((item) => item.available)
      setSelectedModelKey(defaultModel?.key || '')
    })
    const cachedExamId = window.sessionStorage.getItem(RESULT_CACHE_KEY) || window.localStorage.getItem(RESULT_LOCAL_CACHE_KEY)
    if (cachedExamId) {
      examinationApi.get(cachedExamId).then((exam) => {
        setResult(exam)
        setSelectedPatient(exam.patient_id)
        setStep('done')
        rememberExamId(exam.id)
        if (!exam.llm_analysis) {
          startPolling(exam.id)
        }
      }).catch(() => {
        clearRememberedExamId()
        recoverLatestPendingExam()
      })
    } else {
      recoverLatestPendingExam()
    }
    return () => stopPolling()
  }, [])

  const recoverLatestPendingExam = async () => {
    try {
      const exams: ExaminationList[] = await examinationApi.list({ limit: 1 })
      const latest = exams[0]
      if (!latest || latest.risk_level !== 'pending') return
      const exam = await examinationApi.get(latest.id)
      setResult(exam)
      setSelectedPatient(exam.patient_id)
      setStep('done')
      rememberExamId(exam.id)
      if (!exam.llm_analysis) {
        startPolling(exam.id)
      }
    } catch {
      // 静默恢复失败，不影响正常上传流程
    }
  }

  const stepItems = [
    { title: '选择患者', description: '选择或创建患者' },
    { title: '上传图像', description: '结肠镜图像/视频' },
    { title: 'BFNet分割', description: '双模态推理中…' },
    { title: '分析结果', description: 'LLM增强分析' },
  ]

  const currentStep = { select: 0, upload: 1, segmenting: 2, done: 3, error: 3 }[step]

  const handleFileChange = (info: { fileList: UploadFile[] }) => {
    const latest = info.fileList.slice(-1)
    setFileList(latest)
    if (latest[0]?.originFileObj) {
      const url = URL.createObjectURL(latest[0].originFileObj)
      setPreviewUrl(url)
    }
  }

  const handleSubmit = async () => {
    if (!selectedPatient) { message.warning('请先选择患者'); return }
    if (!fileList[0]?.originFileObj) { message.warning('请先上传图像'); return }

    setStep('segmenting')
    setProgress(10)

    try {
      const file = fileList[0].originFileObj as File
      setProgress(30)
      const mergedClinicalNotes = [
        outpatientNotes.trim() ? `门诊问诊信息：${outpatientNotes.trim()}` : '',
        symptomDescription.trim() ? `症状描述：${symptomDescription.trim()}` : '',
        clinicalJudgment.trim() ? `临床判断：${clinicalJudgment.trim()}` : '',
      ].filter(Boolean).join('\n')

      const exam = await examinationApi.upload(selectedPatient, file, mergedClinicalNotes, selectedModelKey, (p) => {
        setProgress(30 + p * 0.5)
      })

      setProgress(100)
      setResult(exam)
      setSelectedPatient(exam.patient_id)
      analysisNotifiedRef.current = false
      rememberExamId(exam.id)
      if (!exam.llm_analysis) {
        startPolling(exam.id)
      }
      setStep('done')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail || (e as { message?: string })?.message || '分割失败'
      setErrorMsg(msg)
      setStep('error')
    }
  }

  const handleReset = () => {
    stopPolling()
    setStep('select')
    setFileList([])
    setPreviewUrl('')
    setResult(null)
    setProgress(0)
    setErrorMsg('')
    setOutpatientNotes('')
    setSymptomDescription('')
    setClinicalJudgment('')
    analysisNotifiedRef.current = false
    clearRememberedExamId()
  }

  const handleAnalyzeNow = async () => {
    if (!result?.id) return
    setIsManualAnalyzing(true)
    setAnalysisSyncText('正在重新触发LLM分析，请保持页面打开')
    try {
      await analysisApi.analyze(result.id, result.llm_model_key || selectedModelKey)
      const latest = await examinationApi.get(result.id)
      setResult(latest)
      setSelectedPatient(latest.patient_id)
      rememberExamId(latest.id)
      if (latest.llm_analysis) {
        message.success('LLM分析已完成，结果已更新')
        stopPolling()
      } else {
        startPolling(latest.id)
      }
    } finally {
      setIsManualAnalyzing(false)
    }
  }

  const riskInfo = result ? RISK_LEVEL_MAP[result.risk_level || 'pending'] : null
  const analysis = result?.llm_analysis
  const selectedModel = modelOptions.find((item) => item.key === selectedModelKey)
  const resultModelLabel = modelOptions.find((item) => item.key === result?.llm_model_key)?.label
    || analysis?.llm_model_label
    || result?.llm_model_key
  const toUploadUrl = (path?: string) => (path ? `/uploads/${path.replace(/\\/g, '/')}` : '')

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-heading">
        <Title level={4} style={{ margin: 0 }}>
          <ExperimentOutlined style={{ marginRight: 8, color: '#1f8fbb' }} />
          息肉分割与智能分析
        </Title>
      </div>

      {/* 步骤条 */}
      <Card style={{ marginBottom: 20 }}>
        <Steps current={currentStep} items={stepItems} size="small" />
      </Card>

      {step === 'error' && (
        <Alert
          type="error"
          showIcon
          message="分割失败"
          description={errorMsg}
          action={<Button size="small" onClick={handleReset}>重试</Button>}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        {/* 左侧：上传区 */}
        <Col xs={24} lg={10}>
          <Card title="图像上传" style={{ height: '100%' }}>
            {/* 患者选择 */}
            <div style={{ marginBottom: 16 }}>
              <Text strong>选择患者 <Text type="danger">*</Text></Text>
              <Select
                style={{ width: '100%', marginTop: 8 }}
                placeholder="请选择患者（输入姓名搜索）"
                showSearch
                filterOption={(input, opt) =>
                  (opt?.label as string)?.toLowerCase().includes(input.toLowerCase())
                }
                value={selectedPatient || undefined}
                onChange={setSelectedPatient}
                options={patients.map(p => ({
                  value: p.id,
                  label: `${p.name}  (${p.gender === 'M' ? '男' : '女'}, ${p.age}岁)`,
                }))}
                notFoundContent={
                  <Space direction="vertical" align="center" style={{ padding: 16 }}>
                    <Text type="secondary">未找到患者</Text>
                    <Button size="small" href="/patients">前往添加患者</Button>
                  </Space>
                }
              />
            </div>

            {/* 上传区 */}
            <Dragger
              className="upload-dragger"
              accept="image/*,video/*"
              fileList={fileList}
              beforeUpload={() => false}
              onChange={handleFileChange}
              showUploadList={false}
              disabled={step === 'segmenting'}
            >
              {previewUrl ? (
                <div>
                  <img
                    src={previewUrl}
                    alt="预览"
                    style={{ maxHeight: 200, maxWidth: '100%', borderRadius: 8 }}
                  />
                  <p style={{ marginTop: 8, color: '#666', fontSize: 12 }}>
                    点击或拖拽可替换图像
                  </p>
                </div>
              ) : (
                <div style={{ padding: '32px 0' }}>
                  <CloudUploadOutlined style={{ fontSize: 48, color: '#1f8fbb', marginBottom: 12 }} />
                  <p style={{ fontSize: 15, fontWeight: 500 }}>点击或拖拽结肠镜图像</p>
                  <p style={{ color: '#999', fontSize: 12, marginTop: 4 }}>支持 JPG / PNG / BMP / MP4</p>
                </div>
              )}
            </Dragger>

            <div style={{ marginTop: 16 }}>
              <Text strong>门诊问诊信息（可选）</Text>
              <Input.TextArea
                style={{ marginTop: 8 }}
                rows={3}
                value={outpatientNotes}
                onChange={(e) => setOutpatientNotes(e.target.value)}
                placeholder="输入门诊问诊信息"
                maxLength={500}
                showCount
                disabled={step === 'segmenting'}
              />
            </div>
            <div style={{ marginTop: 12 }}>
              <Text strong>患者症状描述（可选）</Text>
              <Input.TextArea
                style={{ marginTop: 8 }}
                rows={3}
                value={symptomDescription}
                onChange={(e) => setSymptomDescription(e.target.value)}
                placeholder="输入腹痛、便血、排便习惯变化等症状描述"
                maxLength={500}
                showCount
                disabled={step === 'segmenting'}
              />
            </div>
            <div style={{ marginTop: 12 }}>
              <Text strong>临床判断（可选）</Text>
              <Input.TextArea
                style={{ marginTop: 8 }}
                rows={3}
                value={clinicalJudgment}
                onChange={(e) => setClinicalJudgment(e.target.value)}
                placeholder="输入临床初步判断、关注点或处置方向"
                maxLength={500}
                showCount
                disabled={step === 'segmenting'}
              />
            </div>
            <div style={{ marginTop: 12 }}>
              <Text strong>选择分析模型</Text>
              <Select
                style={{ width: '100%', marginTop: 8 }}
                placeholder="请选择本次分析模型"
                value={selectedModelKey || undefined}
                onChange={setSelectedModelKey}
                disabled={step === 'segmenting'}
                options={modelOptions.map((item) => ({
                  value: item.key,
                  label: `${item.label}${item.default ? '（默认）' : ''}${item.available ? '' : '（未配置）'}`,
                  disabled: !item.available,
                }))}
              />
              {selectedModel && (
                <Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                  本次将使用 {selectedModel.label} 生成医学分析报告
                </Text>
              )}
            </div>

            {/* 提交按钮 */}
            <Button
              type="primary"
              size="large"
              block
              style={{ marginTop: 16, borderRadius: 8 }}
              icon={step === 'segmenting' ? <LoadingOutlined /> : <ExperimentOutlined />}
              loading={step === 'segmenting'}
              disabled={!selectedPatient || !previewUrl || (modelOptions.some((item) => item.available) && !selectedModelKey)}
              onClick={handleSubmit}
            >
              {step === 'segmenting' ? '正在执行BFNet分割…' : '开始分割分析'}
            </Button>

            {step === 'segmenting' && (
              <div style={{ marginTop: 12 }}>
                <Progress percent={progress} status="active" strokeColor="#1f8fbb" />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  BFNet双模态模型推理中，请稍候…
                </Text>
              </div>
            )}
          </Card>
        </Col>

        {/* 右侧：结果展示 */}
        <Col xs={24} lg={14}>
          {step === 'done' && result ? (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              {/* 分割结果图像对比 */}
              <Card
                title={<Space><CheckCircleFilled style={{ color: '#52c41a' }} />分割结果</Space>}
                extra={<span className={`risk-badge-${result.risk_level || 'pending'}`}>{riskInfo?.label}</span>}
              >
                <div className="image-compare">
                  <div>
                    <img src={previewUrl || toUploadUrl(result.image_path)} alt="原始图像" />
                    <div className="img-label">原始图像</div>
                  </div>
                  <div>
                    {result.result_path
                      ? <img src={toUploadUrl(result.result_path)} alt="分割结果" />
                      : <div style={{ height: 200, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Text type="secondary">分割结果图像加载中</Text>
                        </div>
                    }
                    <div className="img-label">BFNet分割结果</div>
                  </div>
                </div>

                {/* 息肉统计 */}
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={8}>
                    <Statistic title="检测到息肉" value={result.polyp_count} suffix="个"
                      valueStyle={{ color: result.polyp_count > 0 ? '#ff4d4f' : '#52c41a' }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="风险等级" value={riskInfo?.label || '待分析'}
                      valueStyle={{ color: riskInfo ? riskColors[result.risk_level as keyof typeof riskColors] : '#1f8fbb' }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="建议复查" value={result.recommended_followup || '—'}
                      suffix={result.recommended_followup ? '天后' : ''} />
                  </Col>
                </Row>
              </Card>

              {/* 息肉详情 */}
              {result.polyps && result.polyps.length > 0 && (
                <Card title="息肉详情">
                  <List
                    dataSource={result.polyps}
                    renderItem={(polyp) => (
                      <List.Item>
                        <Descriptions size="small" column={3} title={`息肉 #${polyp.number}`}>
                          <Descriptions.Item label="直径">{polyp.diameter_mm.toFixed(1)} mm</Descriptions.Item>
                          <Descriptions.Item label="形态">{SHAPE_TYPE_MAP[polyp.shape_type] || polyp.shape_type}</Descriptions.Item>
                          <Descriptions.Item label="置信度">{(polyp.confidence * 100).toFixed(0)}%</Descriptions.Item>
                          <Descriptions.Item label="边界清晰度">
                            <Progress percent={Math.round(polyp.boundary_score * 100)} size="small" showInfo={false} strokeColor="#1f8fbb" />
                          </Descriptions.Item>
                        </Descriptions>
                      </List.Item>
                    )}
                  />
                </Card>
              )}

              {/* LLM 分析报告 */}
              {analysis ? (
                <Card
                  title={<Space><RobotOutlined style={{ color: '#7b61a8' }} />AI 医学分析报告</Space>}
                  extra={<Tag color="purple">LLM增强</Tag>}
                >
                  <Alert
                    type="info"
                    showIcon
                    message="文字说明报告"
                    description={analysis.clinical_report || analysis.doctor_explanation}
                    style={{ marginBottom: 12 }}
                  />
                  <Descriptions column={1} bordered size="small">
                    {resultModelLabel && (
                      <Descriptions.Item label="本次分析模型">{resultModelLabel}</Descriptions.Item>
                    )}
                    <Descriptions.Item label="病理类型预测">{analysis.pathology_type}</Descriptions.Item>
                    {analysis.historical_comparison && (
                      <Descriptions.Item label="历史对比">{analysis.historical_comparison}</Descriptions.Item>
                    )}
                    {analysis.progression_assessment && (
                      <Descriptions.Item label="进展评估">{analysis.progression_assessment}</Descriptions.Item>
                    )}
                    <Descriptions.Item label="医生版解释">
                      <Paragraph style={{ margin: 0 }}>{analysis.doctor_explanation}</Paragraph>
                    </Descriptions.Item>
                    <Descriptions.Item label="患者版解释">
                      <Paragraph style={{ margin: 0, color: '#555' }}>{analysis.patient_explanation}</Paragraph>
                    </Descriptions.Item>
                    <Descriptions.Item label="治疗建议">
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {analysis.treatment_suggestions?.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </Descriptions.Item>
                    <Descriptions.Item label="饮食建议">
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {analysis.dietary_advice?.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </Descriptions.Item>
                    <Descriptions.Item label="随访方案">{analysis.followup_plan}</Descriptions.Item>
                  </Descriptions>
                  <Button
                    type="default"
                    style={{ marginTop: 12 }}
                    onClick={() => {
                      if (result?.id) {
                        window.location.href = `/examinations/${result.id}`
                      }
                    }}
                  >
                    医生审核并确认最终报告
                  </Button>
                </Card>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  icon={<RobotOutlined />}
                  message="LLM分析进行中"
                  description={isPollingAnalysis ? (analysisSyncText || '智能医学分析正在后台生成，完成后会自动显示在当前页面。') : '智能医学分析正在后台生成，可稍后在检查记录或详情页查看完整报告。'}
                  action={
                    <Button
                      size="small"
                      loading={isManualAnalyzing}
                      onClick={handleAnalyzeNow}
                    >
                      重新触发分析
                    </Button>
                  }
                />
              )}

              <Button block onClick={handleReset}>继续上传新图像</Button>
            </Space>
          ) : step === 'segmenting' ? (
            <Card style={{ height: '100%' }}>
              <div style={{ textAlign: 'center', padding: '60px 0' }}>
                <Spin size="large" />
                <Title level={4} style={{ marginTop: 20 }}>BFNet 双模态分割中…</Title>
                <Text type="secondary">
                  正在使用双模态协同注意力网络对图像进行分析
                  <br />
                  模型会同时处理 RGB 图像和深度图信息
                </Text>
                <div style={{ marginTop: 24 }}>
                  <Steps
                    direction="vertical"
                    size="small"
                    current={Math.floor(progress / 25)}
                    items={[
                      { title: '图像预处理', description: '尺寸归一化' },
                      { title: '深度图生成', description: '双模态输入准备' },
                      { title: 'BFNet推理', description: '分割掩码生成' },
                      { title: '结果后处理', description: '轮廓提取与测量' },
                    ]}
                  />
                </div>
              </div>
            </Card>
          ) : (
            <Card style={{ height: '100%' }}>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" align="center">
                    <Text>请在左侧选择患者并上传结肠镜图像</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      系统将使用 BFNet 双模态模型自动识别息肉位置、大小
                      <br />
                      并通过 LLM 生成专业医学分析报告
                    </Text>
                  </Space>
                }
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}

const riskColors: Record<string, string> = {
  high: '#ff4d4f',
  medium: '#fa8c16',
  low: '#52c41a',
  pending: '#1f8fbb',
}
