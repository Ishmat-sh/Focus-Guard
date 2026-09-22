from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CameraStatus:
    available: bool
    message: str


class WebcamCapture:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._capture = None

    def start(self) -> CameraStatus:
        try:
            import cv2
            self._capture = cv2.VideoCapture(self.camera_index)
            if not self._capture.isOpened():
                return CameraStatus(False, "Camera is unavailable")
            return CameraStatus(True, "Camera ready")
        except ImportError:
            return CameraStatus(False, "OpenCV is not installed")

    def read(self):
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        return frame if ok else None

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None