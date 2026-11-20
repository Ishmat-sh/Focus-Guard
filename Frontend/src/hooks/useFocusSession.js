import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../services/api.js";

const EMPTY_SESSION = { state: "idle", elapsed_seconds: 0 };

export function useFocusSession(apiFetch, camera, accessToken) {
  const [session, setSession] = useState(EMPTY_SESSION);
  const [attention, setAttention] = useState(null);
  const [history, setHistory] = useState([]);
  const [browserContext, setBrowserContext] = useState(null);
  const [samples, setSamples] = useState([]);
  const [backendConnected, setBackendConnected] = useState(false);
  const [error, setError] = useState("");
  const lastHistoryRefresh = useRef(0);
  const previousSessionState = useRef("idle");

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      const current = await apiRequest(apiFetch, "/sessions/current");
      const previousState = previousSessionState.current;
      previousSessionState.current = current?.state || "idle";
      setSession(current || EMPTY_SESSION);
      setBackendConnected(true);
      setError("");
      if (
        ["running", "paused"].includes(previousState) &&
        !["running", "paused"].includes(current?.state) &&
        camera.stream
      ) {
        camera.stopCamera();
      }

      const shouldRefreshHistory = Date.now() - lastHistoryRefresh.current >= 15000;
      const [past, context] = await Promise.all([
        shouldRefreshHistory ? apiRequest(apiFetch, "/history") : Promise.resolve(null),
        current?.id && current.state === "running"
          ? apiRequest(apiFetch, "/context/browser")
          : Promise.resolve(null),
      ]);
      if (past) {
        setHistory(past);
        lastHistoryRefresh.current = Date.now();
      }
      setBrowserContext(context);

      if (current?.state === "running" && camera.stream) {
        const frame = await camera.captureFrame();
        if (frame) {
          try {
            const result = await apiRequest(apiFetch, "/attention/frame", {
              method: "POST",
              headers: { "Content-Type": "image/jpeg" },
              body: frame,
            });
            setAttention(result);
            setSamples((previous) => [
              ...previous.slice(-1798),
              {
                elapsed_seconds: current.elapsed_seconds || 0,
                recorded_at: Date.now() / 1000,
                score: result.score,
                state: result.state,
                app_name: result.app_name,
                app_category: result.app_category,
                domain: context?.domain || null,
              },
            ]);
          } catch (frameError) {
            setError(frameError.message || "Could not analyze the current camera frame");
          }
        }
      }
    } catch (requestError) {
      setBackendConnected(false);
      setError(requestError.message || "Could not refresh session data");
    }
  }, [accessToken, apiFetch, camera]);

  useEffect(() => {
    if (!accessToken) {
      setSession(EMPTY_SESSION);
      setAttention(null);
      setHistory([]);
      setBrowserContext(null);
      setSamples([]);
      setBackendConnected(false);
      setError("");
      lastHistoryRefresh.current = 0;
      previousSessionState.current = "idle";
      return undefined;
    }
    let cancelled = false;
    let timer;
    async function poll() {
      await refresh();
      if (!cancelled) timer = window.setTimeout(poll, 1200);
    }
    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [accessToken, refresh]);

  const start = useCallback(async () => {
    setError("");
    try {
      if (!camera.stream) await camera.enableCamera();
      const current = await apiRequest(apiFetch, "/sessions/start", {
        method: "POST",
      });
      setSession(current);
      return current;
    } catch (requestError) {
      setError(requestError.message || "Could not start the focus session");
      throw requestError;
    }
  }, [apiFetch, camera]);

  const pauseOrResume = useCallback(async () => {
    const path = session.state === "paused" ? "/sessions/resume" : "/sessions/pause";
    try {
      const current = await apiRequest(apiFetch, path, { method: "POST" });
      setSession(current);
      setError("");
      return current;
    } catch (requestError) {
      setError(requestError.message || "Could not update the focus session");
      throw requestError;
    }
  }, [apiFetch, session.state]);

  const end = useCallback(async () => {
    try {
      const completed = await apiRequest(apiFetch, "/sessions/end", {
        method: "POST",
      });
      setSession(completed || EMPTY_SESSION);
      camera.stopCamera();
      setError("");
      await refresh();
      return completed;
    } catch (requestError) {
      setError(requestError.message || "Could not end the focus session");
      throw requestError;
    }
  }, [apiFetch, camera, refresh]);

  const focusStreak = (() => {
    let duration = 0;
    for (let index = samples.length - 1; index >= 0; index -= 1) {
      if (samples[index].state !== "focused") break;
      if (index < samples.length - 1) {
        duration += Math.max(
          0,
          samples[index + 1].elapsed_seconds - samples[index].elapsed_seconds,
        );
      }
    }
    return Math.min(duration, session.elapsed_seconds || 0);
  })();

  return {
    session,
    attention,
    history,
    browserContext,
    samples,
    focusStreak,
    backendConnected,
    error,
    setError,
    refresh,
    start,
    pauseOrResume,
    end,
  };
}
