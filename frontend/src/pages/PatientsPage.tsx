import { useState, useEffect } from 'react'
import {
  Table, Button, Card, Typography, Space, Modal, Form, Input,
  Select, InputNumber, Tag, Popconfirm, message, Badge, Empty, Drawer,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, UserOutlined, EditOutlined, DeleteOutlined, EyeOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { patientApi } from '../api'
import type { Patient, PatientCreate } from '../types'

const { Title, Text } = Typography

export default function PatientsPage() {
  const navigate = useNavigate()
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editPatient, setEditPatient] = useState<Patient | null>(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const data = await patientApi.list({ limit: 500 })
      setPatients(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = () => {
    setEditPatient(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleEdit = (patient: Patient) => {
    setEditPatient(patient)
    form.setFieldsValue({
      name: patient.name,
      gender: patient.gender,
      age: patient.age,
      phone: patient.phone,
      medical_history: patient.medical_history,
      allergies: patient.allergies,
      family_history: patient.family_history,
    })
    setModalOpen(true)
  }

  const handleDelete = async (id: string) => {
    await patientApi.delete(id)
    message.success('患者已删除')
    load()
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields() as PatientCreate
      if (editPatient) {
        await patientApi.update(editPatient.id, values)
        message.success('患者信息已更新')
      } else {
        await patientApi.create(values)
        message.success('患者已创建')
      }
      setModalOpen(false)
      load()
    } catch {
      // 表单验证失败
    }
  }

  const filtered = patients.filter(p =>
    !search || p.name.includes(search) || p.phone?.includes(search)
  )

  const columns = [
    {
      title: '患者姓名',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => (
        <Space>
          <UserOutlined style={{ color: '#1f8fbb' }} />
          <Text strong>{v}</Text>
        </Space>
      ),
    },
    {
      title: '性别',
      dataIndex: 'gender',
      key: 'gender',
      width: 70,
      render: (v: string) => (
        <Tag color={v === 'M' ? 'blue' : 'pink'}>{v === 'M' ? '男' : '女'}</Tag>
      ),
    },
    { title: '年龄', dataIndex: 'age', key: 'age', width: 70, render: (v: number) => `${v} 岁` },
    { title: '联系电话', dataIndex: 'phone', key: 'phone' },
    {
      title: '病史摘要',
      dataIndex: 'medical_history',
      key: 'medical_history',
      ellipsis: true,
      render: (v: string) => v ? <Text type="secondary">{v}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('YYYY-MM-DD'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: Patient) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/patients/${record.id}`)}
          >详情</Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确认删除此患者？"
            description="相关检查记录也将被删除"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okType="danger"
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="page-container" style={{ padding: 0 }}>
      <div className="page-toolbar">
        <Title level={4} style={{ margin: 0 }}>
          <UserOutlined style={{ marginRight: 8, color: '#1f8fbb' }} />
          患者管理
          <Badge count={patients.length} style={{ marginLeft: 8, backgroundColor: '#1f8fbb' }} />
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新增患者
        </Button>
      </div>

      <Card>
        <div className="filter-bar">
          <Input
            placeholder="搜索患者姓名或电话…"
            prefix={<SearchOutlined />}
            style={{ width: 280 }}
            value={search}
            onChange={e => setSearch(e.target.value)}
            allowClear
          />
        </div>

        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: <Empty description="暂无患者，请添加" /> }}
          pagination={{ pageSize: 10, showTotal: t => `共 ${t} 位患者` }}
          onRow={record => ({ onDoubleClick: () => navigate(`/patients/${record.id}`) })}
        />
      </Card>

      {/* 新增/编辑 Modal */}
      <Modal
        title={editPatient ? '编辑患者信息' : '新增患者'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editPatient ? '保存' : '创建'}
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="患者姓名" />
          </Form.Item>
          <Form.Item name="gender" label="性别" rules={[{ required: true }]}>
            <Select options={[{ value: 'M', label: '男' }, { value: 'F', label: '女' }]} />
          </Form.Item>
          <Form.Item name="age" label="年龄" rules={[{ required: true, type: 'number', min: 1, max: 150 }]}>
            <InputNumber style={{ width: '100%' }} min={1} max={150} />
          </Form.Item>
          <Form.Item name="phone" label="联系电话" rules={[{ required: true }]}>
            <Input placeholder="手机号码" />
          </Form.Item>
          <Form.Item name="medical_history" label="既往病史">
            <Input.TextArea rows={3} placeholder="如：高血压、糖尿病等（选填）" />
          </Form.Item>
          <Form.Item name="allergies" label="过敏史">
            <Input.TextArea rows={2} placeholder="如：青霉素过敏（选填）" />
          </Form.Item>
          <Form.Item name="family_history" label="家族病史">
            <Input.TextArea rows={2} placeholder="如：结直肠癌家族史（选填）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
