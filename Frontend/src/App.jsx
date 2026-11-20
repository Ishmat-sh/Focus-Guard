import { useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import AuthModal from "./components/AuthModal.jsx";
import Navbar from "./components/Navbar.jsx";
import AppRoutes from "./AppRoutes.jsx";
import { useAppController } from "./hooks/useAppController.js";
import { useMotionPreferences } from "./lib/motion.js";

function App() {
  const app = useAppController();
  const closeAuth = useCallback(() => app.setAuthTab(null), [app.setAuthTab]);
  const motionPreferences = useMotionPreferences();

  return (
    <div className="app-shell">
      <Navbar
        page={app.page}
        setPage={app.setPage}
        userAuth={app.userAuth}
        adminCredentials={app.adminCredentials}
        onOpenAuth={app.openAuth}
        onLogout={app.onLogout}
      />
      {app.notice && (
        <p className="error-banner" role="status" style={{ margin: "0.75rem auto", maxWidth: "1120px" }}>
          {app.notice}
        </p>
      )}
      <AnimatePresence mode="wait">
        <motion.div key={app.page} {...motionPreferences.page}>
          <AppRoutes
            page={app.page}
            apiFetch={app.apiFetch}
            userAuth={app.userAuth}
            isAdmin={app.isAdmin}
            camera={app.camera}
            focusSession={app.focusSession}
            completedSession={app.completedSession}
            onOpenAuth={app.openAuth}
            onStart={app.onStart}
            onSessionComplete={app.onSessionComplete}
            onPasswordChanged={app.onPasswordChanged}
            onLogout={app.onLogout}
            onDashboard={app.onDashboard}
            onCollection={app.onCollection}
            onAdminLogout={app.onAdminLogout}
          />
        </motion.div>
      </AnimatePresence>
      {app.authTab && (
        <AuthModal
          apiFetch={app.apiFetch}
          initialTab={app.authTab}
          onClose={closeAuth}
          onUserAuthenticated={app.onUserAuthenticated}
          onAdminAuthenticated={app.onAdminAuthenticated}
        />
      )}
    </div>
  );
}

export default App;
