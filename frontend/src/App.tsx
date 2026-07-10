import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import JoinPage from './pages/JoinPage';
import TeacherDashboard from './pages/TeacherDashboard';
import StudentDashboard from './pages/StudentDashboard';
import SpacesPage from './pages/SpacesPage';
import StoragePage from './pages/StoragePage';
import RoomPage from './pages/RoomPage';
import ContestsPage from './pages/ContestsPage';
import ContestBuilderPage from './pages/ContestBuilderPage';
import AttemptPage from './pages/AttemptPage';
import SchedulePage from './pages/SchedulePage';
import AnalyticsPage from './pages/AnalyticsPage';
import EditorPage from './pages/EditorPage';
import AssignmentsPage from './pages/AssignmentsPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="content"><div className="skeleton" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function DashboardRedirect() {
  const { user } = useAuth();
  if (!user) return null;
  return <Navigate to={user.role === 'teacher' ? '/dashboard' : '/student'} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/join/:code?" element={<JoinPage />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<DashboardRedirect />} />
            <Route path="dashboard" element={<TeacherDashboard />} />
            <Route path="student" element={<StudentDashboard />} />
            <Route path="spaces" element={<SpacesPage />} />
            <Route path="storage" element={<StoragePage />} />
            <Route path="storage/:materialId" element={<EditorPage />} />
            <Route path="contests" element={<ContestsPage />} />
            <Route path="contests/:id" element={<ContestBuilderPage />} />
            <Route path="assignments" element={<AssignmentsPage />} />
            <Route path="attempts/:id" element={<AttemptPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="room/:lessonId" element={<RoomPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
