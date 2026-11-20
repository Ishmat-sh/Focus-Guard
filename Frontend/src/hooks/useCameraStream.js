import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export function useCameraStream() {
  const streamRef = useRef(
    typeof window !== "undefined" ? window.cameraStream || null : null,
  );
  const videoRef = useRef(null);
  const [stream, setStream] = useState(streamRef.current);
  const [error, setError] = useState("");

  const enableCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("This browser does not support camera access.");
    }
    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = nextStream;
      window.cameraStream = nextStream;
      setStream(nextStream);
      setError("");
      return nextStream;
    } catch (cameraError) {
      const message =
        cameraError.name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser settings."
          : cameraError.message || "Could not access the camera.";
      setError(message);
      throw new Error(message);
    }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (typeof window !== "undefined") window.cameraStream = null;
    setStream(null);
  }, []);

  const captureFrame = useCallback(async () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || !video.videoWidth) return null;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not prepare a camera frame.");
    context.drawImage(video, 0, 0);

    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) resolve(blob);
          else reject(new Error("Could not capture a camera frame."));
        },
        "image/jpeg",
        0.7,
      );
    });
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (video && stream) video.srcObject = stream;
    return () => {
      if (video) video.srcObject = null;
    };
  }, [stream]);

  useEffect(() => stopCamera, [stopCamera]);

  return useMemo(
    () => ({ stream, videoRef, error, enableCamera, stopCamera, captureFrame }),
    [stream, error, enableCamera, stopCamera, captureFrame],
  );
}
