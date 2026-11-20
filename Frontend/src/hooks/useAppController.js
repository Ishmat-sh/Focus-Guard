import { useCallback, useMemo, useRef, useState } from "react";
import { apiRequest, createApiClient } from "../services/api.js";
import { useCameraStream } from "./useCameraStream.js";
import { useFocusSession } from "./useFocusSession.js";

export function useAppController() {
  const [page, setPage] = useState("home");
  const [userAuth, setUserAuth] = useState(null);
  const [adminCredentials, setAdminCredentials] = useState(null);
  const [authTab, setAuthTab] = useState(null);
  const [completedSession, setCompletedSession] = useState(null);
  const [notice, setNotice] = useState("");
  const stateRef = useRef({});
  const camera = useCameraStream();
  stateRef.current = { userAuth, adminCredentials };

  const apiFetch = useMemo(
    () => createApiClient({
      getAccessToken: () => stateRef.current.userAuth?.access_token,
      getAdminCredentials: () => stateRef.current.adminCredentials,
      onUnauthorized: () => {
        setUserAuth(null);
        setAdminCredentials(null);
        setPage("home");
        setNotice("Your sign-in expired. Please sign in again.");
      },
    }),
    [],
  );
  const focusSession = useFocusSession(apiFetch, camera, userAuth?.access_token);
  const openAuth = useCallback((tab = "signin") => setAuthTab(tab), []);
  const onStart = useCallback(() => {
    if (!userAuth) {
      openAuth("signup");
      return;
    }
    setPage("session");
  }, [openAuth, userAuth]);

  const onLogout = useCallback(async () => {
    setNotice("");
    if (userAuth?.access_token) {
      try {
        await apiRequest(apiFetch, "/sessions/end", { method: "POST" });
      } catch (logoutError) {
        if (logoutError.status !== 409) {
          setNotice(logoutError.message || "The session could not be ended before logout.");
        }
      }
      try {
        await apiRequest(apiFetch, "/auth/logout", { method: "POST" });
      } catch (logoutError) {
        setNotice(logoutError.message || "The server could not confirm logout.");
      }
    }
    camera.stopCamera();
    setUserAuth(null);
    setAdminCredentials(null);
    setPage("home");
  }, [apiFetch, camera, focusSession.session.state, userAuth]);

  const onUserAuthenticated = useCallback((result) => {
    setUserAuth(result);
    setAuthTab(null);
    setNotice("");
    setPage(result.user?.must_change_password ? "changePassword" : "session");
  }, []);
  const onAdminAuthenticated = useCallback((credentials) => {
    setAdminCredentials(credentials);
    setAuthTab(null);
    setPage("adminDashboard");
  }, []);
  const onPasswordChanged = useCallback((result) => {
    setUserAuth(result);
    setPage("session");
  }, []);
  const onSessionComplete = useCallback((result) => {
    setCompletedSession(result);
    setPage("summary");
  }, []);
  const onDashboard = useCallback(() => setPage("dashboard"), []);
  const onCollection = useCallback(() => setPage("collection"), []);
  const onAdminLogout = useCallback(() => {
    setAdminCredentials(null);
    setPage("home");
  }, []);

  return {
    page,
    setPage,
    userAuth,
    adminCredentials,
    isAdmin: Boolean(adminCredentials),
    authTab,
    setAuthTab,
    completedSession,
    notice,
    apiFetch,
    camera,
    focusSession,
    openAuth,
    onStart,
    onLogout,
    onUserAuthenticated,
    onAdminAuthenticated,
    onPasswordChanged,
    onSessionComplete,
    onDashboard,
    onCollection,
    onAdminLogout,
  };
}
