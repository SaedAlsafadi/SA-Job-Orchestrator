import { Routes, Route } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import Toaster from '@/components/ui/Toaster';
import OfflineBanner from '@/components/ui/OfflineBanner';
import DashboardPage from '@/pages/DashboardPage';
import JobSearchPage from '@/pages/JobSearchPage';
import ApplicationsPage from '@/pages/ApplicationsPage';
import { CVTailoringWorkbench } from './pages/CVTailoringWorkbench';
import AppDetailPage from '@/pages/AppDetailPage';
import ResumesPage from '@/pages/ResumesPage';
import SettingsPage from '@/pages/SettingsPage';
import AnalyticsPage from '@/pages/AnalyticsPage';
import AdminPage from '@/pages/AdminPage';
import OnboardingPage from '@/pages/OnboardingPage';
import LandingPage from '@/pages/LandingPage';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import ForgotPasswordPage from '@/pages/ForgotPasswordPage';
import SystemStatePage from '@/pages/SystemStatePage';
import { RequireAuth } from '@/components/auth/RequireAuth';
import { RequireSuperuser } from '@/components/auth/RequireSuperuser';
import { PublicOnly } from '@/components/auth/PublicOnly';
import { CandidateProfilePage } from '@/pages/CandidateProfilePage';
import { ApplicationWorkflow } from '@/pages/ApplicationWorkflow';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

function App() {
  const { i18n } = useTranslation();
  useEffect(() => {
    document.documentElement.dir = i18n.dir();
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);
  return (
    <>
      <OfflineBanner />

      <Routes>
        <Route path="/" element={<PublicOnly><LandingPage /></PublicOnly>} />
        <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly redirectTo="/onboarding"><RegisterPage /></PublicOnly>} />
        <Route path="/forgot-password" element={<PublicOnly><ForgotPasswordPage /></PublicOnly>} />
        <Route path="/onboarding" element={<RequireAuth><OnboardingPage /></RequireAuth>} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<CandidateProfilePage />} />
          <Route path="/workflow" element={<ApplicationWorkflow />} />
          <Route path="/jobs" element={<JobSearchPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/applications/:id" element={<AppDetailPage />} />
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/cv-tailoring/:sessionId" element={<CVTailoringWorkbench />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/admin" element={<RequireSuperuser><AdminPage /></RequireSuperuser>} />
          <Route path="*" element={<SystemStatePage code="404" />} />
        </Route>
      </Routes>

      <Toaster />
    </>
  );
}

export default App;






