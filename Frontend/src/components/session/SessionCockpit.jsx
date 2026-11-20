import { useEffect, useRef, useState } from "react";
import TopSessionBar from "./TopSessionBar.jsx";
import FocusCockpit from "./FocusCockpit.jsx";
import DomainContext from "./DomainContext.jsx";
import CameraPreview from "./CameraPreview.jsx";
import SessionControls from "./SessionControls.jsx";

export default function SessionCockpit({
  camera,
  focusSession,
  onComplete,
}) {
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [pending, setPending] = useState(false);
  const previousState = useRef(null);
  const audioContext = useRef(null);
  const { session, attention, focusStreak, browserContext, backendConnected } = focusSession;

  useEffect(() => {
    const nextState = attention?.state;
    if (
      soundEnabled &&
      nextState === "distracted" &&
      previousState.current !== "distracted"
    ) {
      try {
        const Context = window.AudioContext || window.webkitAudioContext;
        if (Context && audioContext.current) {
          const oscillator = audioContext.current.createOscillator();
          const gain = audioContext.current.createGain();
          oscillator.frequency.value = 520;
          gain.gain.setValueAtTime(0.055, audioContext.current.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, audioContext.current.currentTime + 0.18);
          oscillator.connect(gain);
          gain.connect(audioContext.current.destination);
          oscillator.start();
          oscillator.stop(audioContext.current.currentTime + 0.18);
        }
      } catch {
        focusSession.setError("The gentle alert could not play on this device.");
      }
    }
    previousState.current = nextState;
  }, [attention?.state, focusSession, soundEnabled]);

  useEffect(() => () => {
    audioContext.current?.close();
  }, []);

  async function runAction(action) {
    setPending(true);
    try {
      await action();
    } catch {
      // The session hook surfaces the action error in the cockpit.
    } finally {
      setPending(false);
    }
  }

  async function toggleSound() {
    if (!soundEnabled) {
      try {
        const Context = window.AudioContext || window.webkitAudioContext;
        if (Context) {
          audioContext.current = new Context();
          await audioContext.current.resume();
        }
      } catch {
        focusSession.setError("Audio alerts are unavailable in this browser.");
        return;
      }
    }
    setSoundEnabled((enabled) => !enabled);
  }

  return (
    <main className="page-wrap">
      <TopSessionBar
        session={session}
        attention={attention}
        backendConnected={backendConnected}
      />
      {focusSession.error && <p className="error-banner" role="alert">{focusSession.error}</p>}
      {camera.error && <p className="error-banner" role="alert">{camera.error}</p>}
      <div className="session-layout">
        <FocusCockpit attention={attention} focusStreak={focusStreak} />
        <aside className="session-aside">
          <DomainContext session={session} browserContext={browserContext} />
          <SessionControls
            state={session.state}
            cameraEnabled={Boolean(camera.stream)}
            soundEnabled={soundEnabled}
            pending={pending}
            onStart={() => runAction(async () => {
              await focusSession.start();
            })}
            onPauseResume={() => runAction(focusSession.pauseOrResume)}
            onEnd={() => runAction(async () => {
              const completedSession = await focusSession.end();
              onComplete?.(completedSession);
            })}
            onToggleSound={toggleSound}
          />
        </aside>
      </div>
      <CameraPreview
        videoRef={camera.videoRef}
        stream={camera.stream}
        attention={attention}
      />
    </main>
  );
}
