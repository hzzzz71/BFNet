import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import './index.css'

dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1f8fbb',
          colorInfo: '#1f8fbb',
          colorSuccess: '#3aa76d',
          colorWarning: '#d98718',
          colorError: '#d94d4d',
          colorText: '#20242a',
          colorTextSecondary: '#69737f',
          colorBgBase: '#f6f7f8',
          colorBgLayout: '#f6f7f8',
          colorBorder: '#dde3ea',
          colorBorderSecondary: '#edf0f3',
          borderRadius: 8,
          boxShadow: '0 10px 28px rgba(24, 42, 62, 0.07)',
          boxShadowSecondary: '0 6px 18px rgba(24, 42, 62, 0.06)',
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif",
        },
        components: {
          Button: {
            borderRadius: 8,
            controlHeight: 34,
            controlHeightLG: 42,
            primaryShadow: 'none',
          },
          Card: {
            borderRadiusLG: 10,
            paddingLG: 20,
            headerBg: '#ffffff',
          },
          Layout: {
            bodyBg: '#f6f7f8',
            headerBg: '#ffffff',
            siderBg: '#f3f5f1',
            triggerBg: '#e8ece8',
            triggerColor: '#4d5965',
          },
          Menu: {
            itemBg: 'transparent',
            itemSelectedBg: '#ffffff',
            itemSelectedColor: '#1f8fbb',
            itemHoverBg: 'rgba(255,255,255,0.62)',
            itemHoverColor: '#20242a',
            itemBorderRadius: 8,
          },
          Table: {
            headerBg: '#f7f9fa',
            headerColor: '#56616d',
            rowHoverBg: '#f8fbfc',
            borderColor: '#edf0f3',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
)
