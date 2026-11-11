import cv2
import time
from pathlib import Path


class HIKMICRO:
    def __init__(self, camera_index=None, log_callback=None):
        self.log = log_callback if log_callback else print

        if camera_index is None:
            camera_index = self.find_correct_camera()

        if camera_index is None:
            raise RuntimeError("No camera found")

        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {self.camera_index}"
            )

        self.log(f"Using camera index {self.camera_index}")

    def find_correct_camera(self):
        for i in range(10):
            cap = cv2.VideoCapture(i)

            if not cap.isOpened():
                continue

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            self.log(f"Camera {i}: {width}x{height}")

            # likely thermal camera
            if width in (256, 512) or height in (192, 384):
                cap.release()
                return i

            cap.release()

        return 0

    def _check_opened(self):
        return self.cap is not None and self.cap.isOpened()

    def capture_frame(self):
        """Capture a single frame."""
        if not self._check_opened():
            raise RuntimeError("Camera not opened")

        ret, frame = self.cap.read()

        if not ret:
            raise RuntimeError("Failed to capture frame")

        return frame

    def save_jpeg(self, filename=None):
        """Capture and save a JPEG."""

        # some cameras need a moment after opening
        time.sleep(0.2)

        frame = self.capture_frame()

        if filename is None:
            filename = f"thermal_{int(time.time())}.jpg"

        filename = str(Path(filename))

        cv2.imwrite(filename, frame)

        self.log(f"Saved: {filename}")

        return filename

    def live_stream(self):
        """Show live feed. ESC to quit, S to save."""

        if not self._check_opened():
            raise RuntimeError("Camera not opened")

        self.log("ESC = quit")
        self.log("S   = save snapshot")

        while True:
            ret, frame = self.cap.read()

            if not ret:
                self.log("Frame capture failed")
                break

            cv2.imshow("HIKMICRO Thermal", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                break

            elif key == ord("s"):
                filename = f"snapshot_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                self.log(f"Snapshot saved: {filename}")

        cv2.destroyAllWindows()

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        cv2.destroyAllWindows()

    def __del__(self):
        self.release()
    



if __name__ == "__main__":

    try:
        with HIKMICRO() as cam:

            # Save one image
            cam.save_jpeg()

            # Uncomment for live view
            # cam.live_stream()

    except Exception as e:
        print(f"ERROR: {e}")

