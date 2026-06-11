import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import SegmentationPage from './pages/SegmentationPage'
import PatientsPage from './pages/PatientsPage'
import PatientDetail from './pages/PatientDetail'
import ExaminationsPage from './pages/ExaminationsPage'
import ExaminationDetail from './pages/ExaminationDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="segmentation" element={<SegmentationPage />} />
          <Route path="patients" element={<PatientsPage />} />
          <Route path="patients/:id" element={<PatientDetail />} />
          <Route path="examinations" element={<ExaminationsPage />} />
          <Route path="examinations/:id" element={<ExaminationDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
