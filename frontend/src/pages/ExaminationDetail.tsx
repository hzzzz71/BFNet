import { useState, useEffect, useRef } from 'react'
import {
  Card, Descriptions, Tag, Typography, Space, Button, Spin,
  Row, Col, Alert, Divider, List, Progress, Statistic, Badge, Image, Form, Input, Select, message, Modal,
} from 'antd'
import {
  ArrowLeftOutlined, RobotOutlined, ExperimentOutlined,
  CheckCircleFilled, WarningFilled, SafetyCertificateFilled,
  UserOutlined, MedicineBoxOutlined, HeartOutlined,
} from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { examinationApi, patientApi, analysisApi } from '../api'
import type { Examination, Patient, DoctorConfirmedReport, LLMModelOption } from '../types'
import { RISK_LEVEL_MAP, SHAPE_TYPE_MAP } from '../types'

const { Title, Text, Paragraph } = Typography

const riskIcons = {
  high: <WarningFilled style={{ color: '#ff4d4f' }} />,
  medium: <WarningFilled style={{ color: '#fa8c16' }} />,
  low: <SafetyCertificateFilled style={{ color: '#52c41a' }} />,
  pending: <CheckCircleFilled style={{ color: '#1f8fbb' }} />,
}

export default function ExaminationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [exam, setExam] = useState<Examination | null>(null)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [savingReview, setSavingReview] = useState(false)
  const [isEditingReview, setIsEditingReview] = useState(false)
  const [reviewExpanded, setReviewExpanded] = useState(true)
  const [modelOptions, setModelOptions] = useState<LLMModelOption[]>([])
  const [selectedModelKey, setSelectedModelKey] = useState('')
  const [reviewForm] = Form.useForm<DoctorConfirmedReport>()
  const reviewCardRef = useRef<HTMLDivElement | null>(null)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const e = await examinationApi.get(id)
      setExam(e)
      if (e.llm_model_key) {
        setSelectedModelKey(e.llm_model_key)
      }
      const reportSource = e.doctor_confirmed_report || {
        risk_level: e.risk_level || e.llm_analysis?.risk_level || 'low',
        pathology_type: e.pathology_type || e.llm_analysis?.pathology_type || '',
        treatment_recommendation: e.llm_analysis?.treatment_recommendation || '',
        followup_plan: e.llm_analysis?.followup_plan || '',
        clinical_report: e.llm_analysis?.clinical_report || e.llm_analysis?.doctor_explanation || '',
        historical_comparison: e.llm_analysis?.historical_comparison || '',
        progression_assessment: e.llm_analysis?.progression_assessment || '',
      }
      reviewForm.setFieldsValue(reportSource)
      setReviewExpanded(!Boolean(e.doctor_reviewed))
      setIsEditingReview(false)
      if (e.patient_id) {
        const p = await patientApi.get(e.patient_id)
        setPatient(p)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])
  useEffect(() => {
    analysisApi.getModels().then((models) => {
      setModelOptions(models)
      setSelectedModelKey((prev) => {
        if (prev) return prev
        const defaultModel = models.find((item) => item.default && item.available) || models.find((item) => item.available)
        return defaultModel?.key || ''
      })
    })
  }, [])

  const handleAnalyze = async () => {
    if (!id) return
    setAnalyzing(true)
    try {
      await analysisApi.analyze(id, selectedModelKey)
      await load()
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSaveReview = async () => {
    if (!id) return
    try {
      const values = await reviewForm.validateFields()
      setSavingReview(true)
      await analysisApi.saveDoctorReview(id, values)
      message.success('医生确认版报告已保存')
      setIsEditingReview(false)
      setReviewExpanded(false)
      await load()
    } finally {
      setSavingReview(false)
    }
  }

  const handleEditReview = () => {
    setReviewExpanded(true)
    setIsEditingReview(true)
  }

  const handleDownloadReport = async () => {
    if (!id || !exam) return
    if (!exam.doctor_reviewed) {
      setReviewExpanded(true)
      reviewCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      Modal.warning({
        title: '请先完成医生审核与确认',
        content: '正式报告下载需要医生先确认当前检查结果。系统已为你展开定位到确认区域。',
      })
      return
    }
    try {
      const blob = await analysisApi.downloadConfirmedReport(id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      const examDateText = exam.exam_date ? dayjs(exam.exam_date).format('YYYYMMDD') : 'unknown'
      const patientName = patient?.name || '患者'
      a.href = url
      a.download = `${patientName}_${examDateText}_确认版报告.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: Blob } }).response?.data
      if (detail instanceof Blob) {
        const text = await detail.text()
        if (text.includes('请先完成医生审核与确认后再下载正式报告')) {
          setReviewExpanded(true)
          reviewCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          message.warning('请先完成医生审核与确认后再下载正式报告')
        }
      }
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!exam) return <Alert type="error" message="检查记录不存在" />

  const analysis = exam.llm_analysis
  const reviewed = Boolean(exam.doctor_reviewed)
  const confirmedReport = exam.doctor_confirmed_report || {
    risk_level: exam.risk_level || analysis?.risk_level || '',
    pathology_type: exam.pathology_type || analysis?.pathology_type || '',
    treatment_recommendation: analysis?.treatment_recommendation || '',
    followup_plan: analysis?.followup_plan || '',
    clinical_report: analysis?.clinical_report || analysis?.doctor_explanation || '',
    historical_comparison: analysis?.historical_comparison || '',
    progression_assessment: analysis?.progression_assessment || '',
  }
  const riskKey = (exam.risk_level || 'pending') as keyof typeof riskIcons
  const riskInfo = RISK_LEVEL_MAP[exam.risk_level || 'pending']
  const selectedModelLabel = modelOptions.find((item) => item.key === selectedModelKey)?.label
  const currentModelLabel = modelOptions.find((item) => item.key === exam.llm_model_key)?.label
    || analysis?.llm_model_label
    || exam.llm_model_key
  const toUploadUrl = (path?: string) => (path ? `/uploads/${path.replace(/\\/g, '/')}` : '')

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-heading">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/examinations')}>
          返回检查列表
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {/* 左列 */}
        <Col xs={24} lg={10}>
          {/* 检查基本信息 */}
          <Card
            title={<Space><ExperimentOutlined />检查概况</Space>}
            style={{ marginBottom: 16 }}
            extra={<span className={`risk-badge-${riskKey}`}>{riskInfo?.label}</span>}
          >
            <div style={{ textAlign: 'center', padding: '8px 0 20px' }}>
              <div style={{ fontSize: 48 }}>{riskIcons[riskKey]}</div>
              <Title level={3} style={{ margin: '8px 0 4px' }}>
                检测到 {exam.polyp_count} 个息肉
              </Title>
              <Text type="secondary">{dayjs(exam.exam_date).format('YYYY年MM月DD日 HH:mm')}</Text>
            </div>

            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="息肉数量" value={exam.polyp_count} suffix="个"
                  valueStyle={{ color: exam.polyp_count > 0 ? '#ff4d4f' : '#52c41a', fontSize: 22 }} />
              </Col>
              <Col span={8}>
                <Statistic title="建议复查" value={exam.recommended_followup || '—'}
                  suffix={exam.recommended_followup ? '天' : ''} valueStyle={{ fontSize: 22 }} />
              </Col>
              <Col span={8}>
                <Statistic title="检查类型" value="结肠镜" valueStyle={{ fontSize: 18 }} />
              </Col>
            </Row>

            {exam.pathology_type && (
              <>
                <Divider />
              <Descriptions column={1} size="small">
                {currentModelLabel && (
                  <Descriptions.Item label="本次分析模型">{currentModelLabel}</Descriptions.Item>
                )}
                <Descriptions.Item label="病理类型">{exam.pathology_type}</Descriptions.Item>
                {exam.doctor_notes && (
                    <Descriptions.Item label="医生备注">{exam.doctor_notes}</Descriptions.Item>
                  )}
                </Descriptions>
              </>
            )}
          </Card>

          {/* 患者信息 */}
          {patient && (
            <Card
              title={<Space><UserOutlined />患者信息</Space>}
              style={{ marginBottom: 16 }}
              extra={<a onClick={() => navigate(`/patients/${patient.id}`)}>查看档案</a>}
            >
              <Descriptions column={2} size="small">
                <Descriptions.Item label="姓名">{patient.name}</Descriptions.Item>
                <Descriptions.Item label="年龄">{patient.age} 岁</Descriptions.Item>
                <Descriptions.Item label="性别">
                  <Tag color={patient.gender === 'M' ? 'blue' : 'pink'}>
                    {patient.gender === 'M' ? '男' : '女'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="联系电话">{patient.phone}</Descriptions.Item>
                {patient.medical_history && (
                  <Descriptions.Item label="病史" span={2}>
                    <Text type="secondary">{patient.medical_history}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}

          {/* 图像展示 */}
          <Card title="检查图像">
            <div className="image-compare">
              {exam.image_path && (
                <div>
                  <Image
                    src={toUploadUrl(exam.image_path)}
                    alt="原始图像"
                    height={180}
                    style={{ objectFit: 'cover', width: '100%' }}
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                  />
                  <div className="img-label">原始图像</div>
                </div>
              )}
              {exam.result_path && (
                <div>
                  <Image
                    src={toUploadUrl(exam.result_path)}
                    alt="分割结果"
                    height={180}
                    style={{ objectFit: 'cover', width: '100%' }}
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                  />
                  <div className="img-label">BFNet分割结果</div>
                </div>
              )}
            </div>
            {!exam.image_path && !exam.result_path && (
              <Text type="secondary">暂无图像文件</Text>
            )}
          </Card>
        </Col>

        {/* 右列：AI分析报告 */}
        <Col xs={24} lg={14}>
          {analysis ? (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <Card
                title={<Space><RobotOutlined style={{ color: '#7b61a8' }} />文字说明报告</Space>}
                extra={
                  <Space>
                    <Tag color="purple">综合解读</Tag>
                    {reviewed ? <Tag color="success">医生已确认</Tag> : <Tag color="warning">待医生确认</Tag>}
                  </Space>
                }
              >
                <Paragraph style={{ margin: 0, lineHeight: 1.9, whiteSpace: 'pre-wrap' }}>
                  {analysis.clinical_report || analysis.doctor_explanation}
                </Paragraph>
              </Card>

              {/* 医生版解释 */}
              <Card
                title={<Space><MedicineBoxOutlined style={{ color: '#1f8fbb' }} />医生版分析报告</Space>}
                extra={<Tag color="blue">临床专业版</Tag>}
              >
                <Alert
                  type={riskKey === 'high' ? 'error' : riskKey === 'medium' ? 'warning' : 'success'}
                  message={`风险评估：${riskInfo?.label}`}
                  description={analysis.doctor_explanation}
                  showIcon
                  style={{ marginBottom: 16 }}
                />
                {analysis.treatment_suggestions?.length > 0 && (
                  <>
                    <Text strong>治疗建议</Text>
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={analysis.treatment_suggestions}
                      renderItem={(item, i) => (
                        <List.Item style={{ padding: '4px 0' }}>
                          <Space align="start">
                            <Badge count={i + 1} style={{ backgroundColor: '#1f8fbb', fontSize: 10 }} />
                            <Text>{item}</Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </>
                )}
              </Card>

              <Card
                title={<Space><MedicineBoxOutlined style={{ color: '#3aa76d' }} />医生审核与确认</Space>}
                ref={reviewCardRef}
                extra={
                  <Space>
                    <Button onClick={handleDownloadReport}>
                      下载确认版报告
                    </Button>
                    {exam.doctor_reviewed_at && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {dayjs(exam.doctor_reviewed_at).format('YYYY-MM-DD HH:mm')} 已确认
                      </Text>
                    )}
                    {reviewed && !reviewExpanded && (
                      <Button onClick={handleEditReview}>
                        编辑信息
                      </Button>
                    )}
                    {reviewExpanded && (
                      <>
                        <Button onClick={() => setIsEditingReview((prev) => !prev)}>
                          {isEditingReview ? '取消编辑' : '编辑确认版'}
                        </Button>
                        <Button type="primary" loading={savingReview} onClick={handleSaveReview}>
                          保存确认版
                        </Button>
                      </>
                    )}
                  </Space>
                }
              >
                {reviewed && !reviewExpanded ? (
                  <div>
                    <Descriptions column={1} size="small" bordered>
                      <Descriptions.Item label="风险评估">
                        <Text style={{ color: '#000' }}>{RISK_LEVEL_MAP[confirmedReport.risk_level || 'pending']?.label || confirmedReport.risk_level}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="病理倾向">
                        <Text style={{ color: '#000' }}>{confirmedReport.pathology_type}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="确认版报告">
                        <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                          {confirmedReport.clinical_report}
                        </Paragraph>
                      </Descriptions.Item>
                    </Descriptions>
                    <Button style={{ marginTop: 12 }} block onClick={() => setReviewExpanded(true)}>
                      展开
                    </Button>
                  </div>
                ) : (reviewed && reviewExpanded && !isEditingReview) ? (
                  <div>
                    <Descriptions column={1} size="small" bordered>
                      <Descriptions.Item label="风险评估">
                        <Text style={{ color: '#000' }}>{RISK_LEVEL_MAP[confirmedReport.risk_level || 'pending']?.label || confirmedReport.risk_level}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="病理倾向">
                        <Text style={{ color: '#000' }}>{confirmedReport.pathology_type}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="确认版报告">
                        <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                          {confirmedReport.clinical_report}
                        </Paragraph>
                      </Descriptions.Item>
                      <Descriptions.Item label="处置建议">
                        <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                          {confirmedReport.treatment_recommendation}
                        </Paragraph>
                      </Descriptions.Item>
                      <Descriptions.Item label="随访建议">
                        <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                          {confirmedReport.followup_plan}
                        </Paragraph>
                      </Descriptions.Item>
                      {confirmedReport.historical_comparison && (
                        <Descriptions.Item label="历史对比结论">
                          <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                            {confirmedReport.historical_comparison}
                          </Paragraph>
                        </Descriptions.Item>
                      )}
                      {confirmedReport.progression_assessment && (
                        <Descriptions.Item label="进展评估">
                          <Paragraph style={{ margin: 0, color: '#000', whiteSpace: 'pre-wrap' }}>
                            {confirmedReport.progression_assessment}
                          </Paragraph>
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                    <Button style={{ marginTop: 12 }} block onClick={() => setReviewExpanded(false)}>
                      收起
                    </Button>
                  </div>
                ) : (
                  <Form form={reviewForm} layout="vertical">
                    <Row gutter={12}>
                      <Col span={8}>
                        <Form.Item name="risk_level" label="风险评估" rules={[{ required: true, message: '请选择风险等级' }]}>
                          <Select
                            options={[
                              { value: 'low', label: '低风险' },
                              { value: 'medium', label: '中风险' },
                              { value: 'high', label: '高风险' },
                            ]}
                          />
                        </Form.Item>
                      </Col>
                      <Col span={16}>
                        <Form.Item name="pathology_type" label="病理倾向" rules={[{ required: true, message: '请输入病理倾向' }]}>
                          <Input placeholder="输入病理倾向" />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name="clinical_report" label="医生确认版医学报告" rules={[{ required: true, message: '请输入确认版报告' }]}>
                      <Input.TextArea rows={6} placeholder="可基于AI结果进行修改与确认，作为最终医生确认版报告" />
                    </Form.Item>
                    <Form.Item name="treatment_recommendation" label="处置建议" rules={[{ required: true, message: '请输入处置建议' }]}>
                      <Input.TextArea rows={3} placeholder="输入最终处置建议" />
                    </Form.Item>
                    <Form.Item name="followup_plan" label="随访建议" rules={[{ required: true, message: '请输入随访建议' }]}>
                      <Input.TextArea rows={3} placeholder="输入随访建议" />
                    </Form.Item>
                    <Form.Item name="historical_comparison" label="历史对比结论">
                      <Input.TextArea rows={2} placeholder="填写与既往检查的对比结果" />
                    </Form.Item>
                    <Form.Item name="progression_assessment" label="进展评估">
                      <Input.TextArea rows={2} placeholder="填写增大/增多/稳定/好转等进展评估" />
                    </Form.Item>
                  </Form>
                )}
              </Card>

              {/* 患者版解释 */}
              <Card
                title={<Space><UserOutlined style={{ color: '#52c41a' }} />患者版通俗说明</Space>}
                extra={<Tag color="green">患者友好版</Tag>}
              >
                <Paragraph style={{ fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                  {analysis.patient_explanation}
                </Paragraph>
              </Card>

              {/* 随访方案 */}
              <Card
                title={<Space><HeartOutlined style={{ color: '#fa8c16' }} />随访与健康管理</Space>}
              >
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label="随访方案">
                    {analysis.followup_plan}
                  </Descriptions.Item>
                </Descriptions>

                {analysis.dietary_advice?.length > 0 && (
                  <>
                    <Divider orientation="left" style={{ fontSize: 13 }}>饮食与生活建议</Divider>
                    <List
                      size="small"
                      dataSource={analysis.dietary_advice}
                      renderItem={(item) => (
                        <List.Item style={{ padding: '4px 0' }}>
                          <Space align="start">
                            <CheckCircleFilled style={{ color: '#52c41a' }} />
                            <Text>{item}</Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </>
                )}
              </Card>

              {/* 息肉详情 */}
              {exam.polyps && exam.polyps.length > 0 && (
                <Card title="息肉详情分析">
                  {exam.polyps.map(polyp => (
                    <div key={polyp.number} style={{ marginBottom: 12 }}>
                      <Text strong>息肉 #{polyp.number}</Text>
                      <Row gutter={8} style={{ marginTop: 8 }}>
                        <Col span={8}>
                          <Text type="secondary" style={{ fontSize: 12 }}>直径</Text>
                          <div><Text strong>{polyp.diameter_mm.toFixed(1)} mm</Text></div>
                        </Col>
                        <Col span={8}>
                          <Text type="secondary" style={{ fontSize: 12 }}>形态</Text>
                          <div><Text strong>{SHAPE_TYPE_MAP[polyp.shape_type] || polyp.shape_type}</Text></div>
                        </Col>
                        <Col span={8}>
                          <Text type="secondary" style={{ fontSize: 12 }}>置信度</Text>
                          <div>
                            <Progress
                              percent={Math.round(polyp.confidence * 100)}
                              size="small"
                              strokeColor="#1f8fbb"
                            />
                          </div>
                        </Col>
                      </Row>
                      <Divider style={{ margin: '8px 0' }} />
                    </div>
                  ))}
                </Card>
              )}
            </Space>
          ) : (
            <Card style={{ height: '100%' }}>
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <RobotOutlined style={{ fontSize: 56, color: '#7b61a8', marginBottom: 16 }} />
                <Title level={4}>AI 医学分析报告</Title>
                <Paragraph type="secondary">
                  LLM分析报告尚未生成。
                  <br />
                  点击下方按钮立即触发 LLM 分析，
                  <br />
                  将自动生成医患双版本解释和随访建议。
                </Paragraph>
                <Button
                  type="primary"
                  size="large"
                  icon={<RobotOutlined />}
                  loading={analyzing}
                  onClick={handleAnalyze}
                  style={{ marginTop: 8 }}
                  disabled={modelOptions.some((item) => item.available) && !selectedModelKey}
                >
                  {analyzing ? '分析中…' : '立即生成 LLM 分析报告'}
                </Button>
                <Select
                  style={{ marginTop: 12, width: 320, maxWidth: '100%' }}
                  placeholder="请选择本次分析模型"
                  value={selectedModelKey || undefined}
                  onChange={setSelectedModelKey}
                  options={modelOptions.map((item) => ({
                    value: item.key,
                    label: `${item.label}${item.default ? '（默认）' : ''}${item.available ? '' : '（未配置）'}`,
                    disabled: !item.available,
                  }))}
                />
                {selectedModelLabel && (
                  <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                    本次将使用 {selectedModelLabel} 生成医学分析报告。
                  </Paragraph>
                )}
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
