import { useState, useEffect } from 'react'
import {
  Card, Descriptions, Tag, Typography, Space, Button, Spin,
  Table, Timeline, Empty, Statistic, Row, Col, Alert, Divider, Upload, List, Popconfirm, message,
} from 'antd'
import {
  ArrowLeftOutlined, ExperimentOutlined, UserOutlined, FileSearchOutlined,
  UploadOutlined, FileTextOutlined, DownloadOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { patientApi, examinationApi } from '../api'
import type { UploadRequestOption } from 'rc-upload/lib/interface'
import type { Patient, ExaminationList, PatientReport } from '../types'
import { RISK_LEVEL_MAP } from '../types'

const { Title, Text } = Typography

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [exams, setExams] = useState<ExaminationList[]>([])
  const [reports, setReports] = useState<PatientReport[]>([])
  const [uploadingReport, setUploadingReport] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const loadAll = async (patientId: string) => {
    const [p, e, r] = await Promise.all([
      patientApi.get(patientId),
      examinationApi.list({ patient_id: patientId }).catch(() => []),
      patientApi.listReports(patientId).catch(() => []),
    ])
    setPatient(p)
    setExams(e)
    setReports(r)
  }

  useEffect(() => {
    if (!id) return
    setLoadError('')
    loadAll(id).catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
      const detail = err?.response?.data?.detail || err?.message || '患者详情加载失败'
      setLoadError(detail)
      setPatient(null)
      setExams([])
      setReports([])
    }).finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (loadError) return <Alert type="error" message={loadError} />
  if (!patient) return <Alert type="error" message="患者不存在" />

  const riskCount = exams.reduce((acc, e) => {
    const k = e.risk_level || 'pending'
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const examColumns = [
    { title: '检查时间', dataIndex: 'exam_date', key: 'exam_date', render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: '息肉数量', dataIndex: 'polyp_count', key: 'polyp_count', render: (v: number) => <Tag color={v > 0 ? 'red' : 'green'}>{v} 个</Tag> },
    {
      title: '风险等级', dataIndex: 'risk_level', key: 'risk_level',
      render: (v: string) => {
        const info = RISK_LEVEL_MAP[v || 'pending']
        return <span className={`risk-badge-${v || 'pending'}`}>{info?.label}</span>
      }
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, row: ExaminationList) => (
        <Button size="small" onClick={() => navigate(`/examinations/${row.id}`)}>查看详情</Button>
      )
    },
  ]

  const handleReportUpload = async (options: UploadRequestOption) => {
    if (!id) return
    const file = options.file as File
    const ext = `.${(file.name.split('.').pop() || '').toLowerCase()}`
    if (!['.pdf', '.doc', '.docx'].includes(ext)) {
      message.warning('仅支持 PDF、DOC、DOCX 格式报告')
      options.onError?.(new Error('invalid_file_type'))
      return
    }

    setUploadingReport(true)
    try {
      await patientApi.uploadReport(id, file)
      const latestReports = await patientApi.listReports(id)
      setReports(latestReports)
      message.success('病例报告上传成功')
      options.onSuccess?.({}, file)
    } catch (error) {
      options.onError?.(error as Error)
    } finally {
      setUploadingReport(false)
    }
  }

  const handleDeleteReport = async (reportId: string) => {
    if (!id) return
    await patientApi.deleteReport(id, reportId)
    setReports(prev => prev.filter(report => report.id !== reportId))
    message.success('报告已删除')
  }

  const formatFileSize = (size?: number) => {
    if (!size || size <= 0) return '未知大小'
    if (size < 1024) return `${size} B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-heading">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/patients')}>
          返回患者列表
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {/* 患者基本信息 */}
        <Col xs={24} lg={8}>
          <Card
            title={<Space><UserOutlined />患者档案</Space>}
            extra={
              <Button size="small" icon={<ExperimentOutlined />}
                onClick={() => navigate('/segmentation')}>
                新建检查
              </Button>
            }
          >
            <Descriptions column={1} size="small">
              <Descriptions.Item label="姓名">
                <Text strong style={{ fontSize: 16 }}>{patient.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="性别">
                <Tag color={patient.gender === 'M' ? 'blue' : 'pink'}>
                  {patient.gender === 'M' ? '男' : '女'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="年龄">{patient.age} 岁</Descriptions.Item>
              <Descriptions.Item label="联系电话">{patient.phone || '—'}</Descriptions.Item>
              <Descriptions.Item label="既往病史">
                <Text type="secondary">{patient.medical_history || '无'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="过敏史">
                <Text type="secondary">{patient.allergies || '无'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="家族病史">
                <Text type="secondary">{patient.family_history || '无'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {dayjs(patient.created_at).format('YYYY-MM-DD')}
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            {/* 统计摘要 */}
            <Row gutter={12}>
              <Col span={12}>
                <Statistic title="检查次数" value={exams.length} suffix="次" />
              </Col>
              <Col span={12}>
                <Statistic
                  title="高风险记录"
                  value={riskCount.high || 0}
                  suffix="次"
                  valueStyle={{ color: (riskCount.high || 0) > 0 ? '#ff4d4f' : '#52c41a' }}
                />
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 检查历史 */}
        <Col xs={24} lg={16}>
          <Card
            title={<Space><FileSearchOutlined />检查历史记录</Space>}
          >
            {exams.length === 0 ? (
              <Empty description="暂无检查记录" />
            ) : (
              <Table
                dataSource={exams}
                columns={examColumns}
                rowKey="id"
                pagination={{ pageSize: 8 }}
                size="small"
              />
            )}
          </Card>

          {/* 时间轴 */}
          {exams.length > 0 && (
            <Card title="检查时间轴" style={{ marginTop: 16 }}>
              <Timeline
                items={exams.slice(0, 6).map(e => ({
                  color: e.risk_level === 'high' ? 'red' : e.risk_level === 'medium' ? 'orange' : 'green',
                  children: (
                    <div>
                      <Text strong>{dayjs(e.exam_date).format('YYYY-MM-DD')}</Text>
                      <span style={{ marginLeft: 8 }}>
                        <span className={`risk-badge-${e.risk_level || 'pending'}`}>
                          {RISK_LEVEL_MAP[e.risk_level || 'pending']?.label}
                        </span>
                      </span>
                      <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                        检出 {e.polyp_count} 个息肉
                      </Text>
                    </div>
                  )
                }))}
              />
            </Card>
          )}

          <Card
            title={<Space><FileTextOutlined />病例报告</Space>}
            style={{ marginTop: 16 }}
            extra={
              <Upload
                showUploadList={false}
                customRequest={handleReportUpload}
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={uploadingReport}
              >
                <Button size="small" icon={<UploadOutlined />} loading={uploadingReport}>
                  上传报告
                </Button>
              </Upload>
            }
          >
            {reports.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无上传报告" />
            ) : (
              <List
                dataSource={reports}
                renderItem={(report) => (
                  <List.Item
                    actions={[
                      <a key="download" href={report.download_url} target="_blank" rel="noreferrer">
                        <Space size={4}><DownloadOutlined />下载</Space>
                      </a>,
                      <Popconfirm
                        key="delete"
                        title="确认删除该报告？"
                        onConfirm={() => handleDeleteReport(report.id)}
                        okText="删除"
                        cancelText="取消"
                      >
                        <Button type="link" danger style={{ padding: 0 }}>
                          <Space size={4}><DeleteOutlined />删除</Space>
                        </Button>
                      </Popconfirm>,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<FileTextOutlined />}
                      title={report.file_name}
                      description={`上传时间：${dayjs(report.uploaded_at).format('YYYY-MM-DD HH:mm')} · ${formatFileSize(report.file_size)}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
