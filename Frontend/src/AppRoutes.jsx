import HomeView from "./components/HomeView.jsx";
import SessionCockpit from "./components/session/SessionCockpit.jsx";
import DashboardView from "./components/dashboard/DashboardView.jsx";
import AdminDashboard from "./components/admin/AdminDashboard.jsx";
import {
  AnalyticsView,
  ChangePasswordView,
  CoachingView,
  CollectionView,
  SettingsView,
  SummaryView,
} from "./components/FeaturePages.jsx";

export default function AppRoutes({
  page,
  apiFetch,
  userAuth,
  isAdmin,
  camera,
  focusSession,
  completedSession,
  onOpenAuth,
  onStart,
  onSessionComplete,
  onPasswordChanged,
  onLogout,
  onDashboard,
  onCollection,
  onAdminLogout,
}) {
  if (page === "home") {
    return <HomeView onOpenAuth={onOpenAuth} onStart={onStart} />;
  }
  if (page === "session") {
    return (
      <SessionCockpit
        camera={camera}
        focusSession={focusSession}
        onComplete={onSessionComplete}
      />
    );
  }
  if (page === "dashboard") {
    return <DashboardView apiFetch={apiFetch} onStart={onStart} onCollection={onCollection} />;
  }
  if (page === "analytics") return <AnalyticsView apiFetch={apiFetch} />;
  if (page === "coaching") return <CoachingView apiFetch={apiFetch} />;
  if (page === "settings") return <SettingsView apiFetch={apiFetch} />;
  if (page === "collection") {
    return <CollectionView apiFetch={apiFetch} onBack={onDashboard} />;
  }
  if (page === "summary") {
    return (
      <SummaryView
        session={completedSession}
        onDashboard={onDashboard}
        onStart={onStart}
      />
    );
  }
  if (page === "changePassword") {
    return (
      <ChangePasswordView
        apiFetch={apiFetch}
        onComplete={onPasswordChanged}
        onLogout={onLogout}
      />
    );
  }
  if (page === "adminDashboard" && isAdmin && userAuth == null) {
    return <AdminDashboard apiFetch={apiFetch} onLogout={onAdminLogout} />;
  }
  return <HomeView onOpenAuth={onOpenAuth} onStart={onStart} />;
}
