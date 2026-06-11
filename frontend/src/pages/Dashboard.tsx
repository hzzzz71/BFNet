import { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Table, Tag, Typography, Space, Alert, Spin, Timeline, Progress } from 'antd'
import {
  TeamOutlined,
  FileSearchOutlined,
  AlertOutlined,
  ClockCircleOutlined,
  RiseOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { patientApi, examinationApi } from '../api'
import type { ExaminationList } from '../types'
import { RISK_LEVEL_MAP } from '../types'

const { Title, Text } = Typography

const riskColors = {
  high: '#ff4d4f',
  medium: '#fa8c16',
  low: '#52c41a',
  pending: '#1f8fbb',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total_patients: 0, total_examinations: 0, high_risk: 0, pending: 0 })
  const [recentExams, setRecentExams] = useState<ExaminationList[]>([])
  const [riskDist, setRiskDist] = useState({ low: 0, medium: 0, high: 0, pending: 0 })

  useEffect(() => {
    const load = async () => {
      try {
        const [patients, exams] = await Promise.all([
          patientApi.list({ limit: 1000 }),
          examinationApi.list({ limit: 1000 }),
        ])
        const dist = { low: 0, medium: 0, high: 0, pending: 0 }
        exams.forEach(e => {
          const k = (e.risk_level || 'pending') as keyof typeof dist
          if (k in dist) dist[k]++
          else dist.pending++
        })
        setStats({
          total_patients: patients.length,
          total_examinations: exams.length,
          high_risk: dist.high,
          pending: dist.pending,
        })
        setRiskDist(dist)
        setRecentExams(exams.slice(0, 8))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const columns = [
    { title: '检查ID', dataIndex: 'id', key: 'id', width: 80, render: (v: string) => <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}…</Text> },
    { title: '检查时间', dataIndex: 'exam_date', key: 'exam_date', render: (v: string) => dayjs(v).format('MM-DD HH:mm') },
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
        <a onClick={() => navigate(`/examinations/${row.id}`)}>查看详情</a>
      )
    },
  ]

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" tip="加载中…" /></div>

  const total = stats.total_examinations || 1

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-heading">
        <Title level={4} style={{ margin: 0 }}>
          <ExperimentOutlined style={{ marginRight: 8, color: '#1f8fbb' }} />
          系统概览
        </Title>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {[
          { title: '患者总数', value: stats.total_patients, icon: <TeamOutlined />, color: '#1f8fbb', suffix: '人', onClick: () => navigate('/patients') },
          { title: '检查总数', value: stats.total_examinations, icon: <FileSearchOutlined />, color: '#7b61a8', suffix: '次', onClick: () => navigate('/examinations') },
          { title: '高风险病例', value: stats.high_risk, icon: <AlertOutlined />, color: '#ff4d4f', suffix: '例', onClick: () => navigate('/examinations') },
          { title: '待分析', value: stats.pending, icon: <ClockCircleOutlined />, color: '#fa8c16', suffix: '个', onClick: () => navigate('/examinations') },
        ].map(item => (
          <Col xs={24} sm={12} lg={6} key={item.title}>
            <Card
              hoverable
              className="card-hover metric-card"
              onClick={item.onClick}
              style={{ cursor: 'pointer' }}
              styles={{ body: { padding: '20px 24px' } }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Statistic
                  title={<Text type="secondary" style={{ fontSize: 13 }}>{item.title}</Text>}
                  value={item.value}
                  suffix={item.suffix}
                  valueStyle={{ color: item.color, fontWeight: 700, fontSize: 28 }}
                />
                <div className="metric-icon" style={{ background: item.color + '15', color: item.color }}>
                  {item.icon}
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        {/* 最近检查记录 */}
        <Col xs={24} lg={16}>
          <Card
            title={<Space><FileSearchOutlined />最近检查记录</Space>}
            extra={<a onClick={() => navigate('/examinations')}>查看全部</a>}
          >
            {recentExams.length === 0
              ? <Alert message="暂无检查记录，请先上传图像进行分析" type="info" showIcon />
              : <Table
                  dataSource={recentExams}
                  columns={columns}
                  rowKey="id"
                  pagination={false}
                  size="small"
                />
            }
          </Card>
        </Col>

        {/* 风险分布 */}
        <Col xs={24} lg={8}>
          <Card title={<Space><RiseOutlined />风险等级分布</Space>} style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={14}>
              {[
                { key: 'high', label: '高风险', color: '#ff4d4f' },
                { key: 'medium', label: '中风险', color: '#fa8c16' },
                { key: 'low', label: '低风险', color: '#52c41a' },
                { key: 'pending', label: '待分析', color: '#1f8fbb' },
              ].map(item => (
                <div key={item.key}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <Text style={{ fontSize: 13 }}>{item.label}</Text>
                    <Text strong style={{ fontSize: 13, color: item.color }}>
                      {riskDist[item.key as keyof typeof riskDist]} 例
                    </Text>
                  </div>
                  <Progress
                    percent={Math.round(riskDist[item.key as keyof typeof riskDist] / total * 100)}
                    strokeColor={item.color}
                    showInfo={false}
                    size="small"
                  />
                </div>
              ))}
            </Space>
          </Card>

          {/* 快速操作 */}
          <Card title="快速操作">
            <Timeline
              items={[
                {
                  color: 'blue',
                  children: <a onClick={() => navigate('/segmentation')}>上传图像 → 立即分析</a>
                },
                {
                  color: 'green',
                  children: <a onClick={() => navigate('/patients')}>添加新患者档案</a>
                },
                {
                  color: 'orange',
                  children: <a onClick={() => navigate('/examinations')}>查看所有检查记录</a>
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
