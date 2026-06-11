import { useState, useEffect } from 'react'
import {
  Card, Table, Tag, Typography, Space, Select, Button,
  Input, Badge, Empty, Statistic, Row, Col,
} from 'antd'
import {
  FileSearchOutlined, SearchOutlined, FilterOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { examinationApi, patientApi } from '../api'
import type { ExaminationList, Patient } from '../types'
import { RISK_LEVEL_MAP } from '../types'

const { Title, Text } = Typography

export default function ExaminationsPage() {
  const navigate = useNavigate()
  const [exams, setExams] = useState<ExaminationList[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(false)
  const [filterPatient, setFilterPatient] = useState<string>('')
  const [filterRisk, setFilterRisk] = useState<string>('')

  const load = async () => {
    setLoading(true)
    try {
      const [e, p] = await Promise.all([
        examinationApi.list({ limit: 500, patient_id: filterPatient || undefined }),
        patientApi.list({ limit: 500 }),
      ])
      setExams(e)
      setPatients(p)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filterPatient])

  const patientMap = Object.fromEntries(patients.map(p => [p.id, p]))

  const filtered = exams.filter(e => !filterRisk || (e.risk_level || 'pending') === filterRisk)

  const stats = {
    total: filtered.length,
    high: filtered.filter(e => e.risk_level === 'high').length,
    medium: filtered.filter(e => e.risk_level === 'medium').length,
    low: filtered.filter(e => e.risk_level === 'low').length,
  }

  const columns = [
    {
      title: '检查时间',
      dataIndex: 'exam_date',
      key: 'exam_date',
      sorter: (a: ExaminationList, b: ExaminationList) => dayjs(a.exam_date).unix() - dayjs(b.exam_date).unix(),
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '患者姓名',
      dataIndex: 'patient_id',
      key: 'patient_id',
      render: (v: string) => {
        const p = patientMap[v]
        return p ? (
          <a onClick={() => navigate(`/patients/${v}`)}>
            {p.name} <Text type="secondary" style={{ fontSize: 12 }}>({p.age}岁{p.gender === 'M' ? '男' : '女'})</Text>
          </a>
        ) : <Text type="secondary">{v.slice(0, 8)}…</Text>
      },
    },
    {
      title: '息肉数量',
      dataIndex: 'polyp_count',
      key: 'polyp_count',
      sorter: (a: ExaminationList, b: ExaminationList) => a.polyp_count - b.polyp_count,
      render: (v: number) => (
        <Tag color={v === 0 ? 'green' : v <= 2 ? 'orange' : 'red'} style={{ fontWeight: 600 }}>
          {v} 个
        </Tag>
      ),
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      filters: [
        { text: '高风险', value: 'high' },
        { text: '中风险', value: 'medium' },
        { text: '低风险', value: 'low' },
        { text: '待分析', value: 'pending' },
      ],
      onFilter: (value: React.Key | boolean, record: ExaminationList) =>
        (record.risk_level || 'pending') === value,
      render: (v: string) => {
        const info = RISK_LEVEL_MAP[v || 'pending']
        return <span className={`risk-badge-${v || 'pending'}`}>{info?.label}</span>
      },
    },
    {
      title: '检查类型',
      dataIndex: 'exam_type',
      key: 'exam_type',
      render: (v: string) => <Tag>结肠镜</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: ExaminationList) => (
        <Button size="small" type="link" onClick={() => navigate(`/examinations/${row.id}`)}>
          查看报告
        </Button>
      ),
    },
  ]

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-toolbar">
        <Title level={4} style={{ margin: 0 }}>
          <FileSearchOutlined style={{ marginRight: 8, color: '#1f8fbb' }} />
          检查记录
          <Badge count={exams.length} style={{ marginLeft: 8, backgroundColor: '#1f8fbb' }} />
        </Title>
        <Button type="primary" icon={<FileSearchOutlined />} onClick={() => navigate('/segmentation')}>
          新建检查
        </Button>
      </div>

      {/* 统计行 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {[
          { label: '全部', value: stats.total, color: '#1f8fbb' },
          { label: '高风险', value: stats.high, color: '#ff4d4f' },
          { label: '中风险', value: stats.medium, color: '#fa8c16' },
          { label: '低风险', value: stats.low, color: '#52c41a' },
        ].map(s => (
          <Col key={s.label}>
            <Card size="small" className="metric-card" style={{ minWidth: 100 }}>
              <Statistic
                title={<Text style={{ fontSize: 12 }}>{s.label}</Text>}
                value={s.value}
                suffix="次"
                valueStyle={{ color: s.color, fontSize: 20 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card>
        {/* 筛选栏 */}
        <div className="filter-bar">
          <Select
            style={{ width: 200 }}
            placeholder="筛选患者"
            allowClear
            showSearch
            filterOption={(input, opt) => (opt?.label as string)?.toLowerCase().includes(input.toLowerCase())}
            onChange={setFilterPatient}
            options={patients.map(p => ({ value: p.id, label: `${p.name} (${p.age}岁)` }))}
          />
          <Select
            style={{ width: 130 }}
            placeholder="风险等级"
            allowClear
            onChange={setFilterRisk}
            options={[
              { value: 'high', label: '高风险' },
              { value: 'medium', label: '中风险' },
              { value: 'low', label: '低风险' },
              { value: 'pending', label: '待分析' },
            ]}
          />
          <Button icon={<FilterOutlined />} onClick={load}>刷新</Button>
        </div>

        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: <Empty description="暂无检查记录" /> }}
          pagination={{ pageSize: 10, showTotal: t => `共 ${t} 条记录` }}
          onRow={row => ({ onDoubleClick: () => navigate(`/examinations/${row.id}`) })}
        />
      </Card>
    </div>
  )
}
