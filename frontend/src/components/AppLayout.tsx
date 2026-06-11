import { useState, useEffect } from 'react'
import { Layout, Menu, Badge, Tooltip, Typography } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined,
  ExperimentOutlined,
  TeamOutlined,
  FileSearchOutlined,
  HeartOutlined,
} from '@ant-design/icons'
import { systemApi } from '../api'

const { Sider, Header, Content, Footer } = Layout
const { Text } = Typography

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/segmentation', icon: <ExperimentOutlined />, label: '息肉分割' },
  { key: '/patients', icon: <TeamOutlined />, label: '患者管理' },
  { key: '/examinations', icon: <FileSearchOutlined />, label: '检查记录' },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [health, setHealth] = useState<{ status: string; model: string; database: string } | null>(null)

  useEffect(() => {
    systemApi.health().then(setHealth)
    const t = setInterval(() => systemApi.health().then(setHealth), 30000)
    return () => clearInterval(t)
  }, [])

  const selectedKey = '/' + location.pathname.split('/')[1]
  const healthy = health?.status === 'healthy'

  return (
    <Layout className="app-shell">
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="light"
        className="app-sider"
        width={220}
      >
        <div className={`app-brand ${collapsed ? 'app-brand-collapsed' : ''}`}>
          <span className="app-brand-icon">
            <HeartOutlined />
          </span>
          {!collapsed && (
            <span className="app-brand-copy">
              <Text className="app-brand-title">智能息肉诊疗平台</Text>
              <Text className="app-brand-subtitle">BFNet + LLM 医学工作台</Text>
            </span>
          )}
        </div>

        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          className="app-menu"
        />

      </Sider>

      <Layout>
        <Header className="app-header">
          <div className="app-header-title">
            <Text strong>智能息肉诊疗辅助平台</Text>
            <Text type="secondary">基于 BFNet 双模态分割 + LLM 医学分析</Text>
          </div>
          <div className="app-header-actions">
            {health && (
              <Tooltip title={`模型: ${health.model} | 数据库: ${health.database}`}>
                <span className={`health-pill ${healthy ? 'health-pill-ok' : 'health-pill-error'}`}>
                  <Badge status={healthy ? 'success' : 'error'} />
                  <Text>{healthy ? '系统正常' : '系统异常'}</Text>
                </span>
              </Tooltip>
            )}
          </div>
        </Header>

        <Content className="app-content">
          <Outlet />
        </Content>

        <Footer className="app-footer">
          智能息肉诊疗辅助平台 v1.0 · 基于BFNet双模态协同注意力网络 · 毕业设计
        </Footer>
      </Layout>
    </Layout>
  )
}
