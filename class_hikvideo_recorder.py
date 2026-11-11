# class_hikvideo_recorder.py

import json
import shutil
import tempfile
import time

import numpy as np

from pathlib import Path
from datetime import datetime

from class_hikmodels import *


class VideoRecorder:

    CHUNK_SIZE = 1000

    def __init__(self, camera):
        self.cam = camera
        self.is_recording = False
        self.first_timestamp = None
        self.last_timestamp = None
        self.frame_count = 0
        self.chunk_index = 0
        self.raw_frames = []
        self.raw_timestamps = []

        self.temp_dir = None

    # -------------------------------------------------
    # Recording control
    # -------------------------------------------------

    def start(self):
        if self.is_recording:
            return
        settings = self.cam.video_settings
        stamp = ""

        if settings.append_timestamp:
            stamp = datetime.now().strftime(
                "_%Y%m%d_%H%M%S"
            )

        self.base_name = (
            settings.filename_prefix + stamp
        )

        self.start_time = time.time()

        self.first_timestamp = None
        self.last_timestamp = None

        self.frame_count = 0
        self.chunk_index = 0

        self.raw_frames.clear()
        self.raw_timestamps.clear()

        self.temp_dir = Path(
            tempfile.mkdtemp(
                prefix=f"{self.base_name}_"
            )
        )

        self.is_recording = True

        self.cam.state.is_video_recording = True

        self.cam.emit_event(
            CameraEvent.VIDEO_REC_STARTED
        )

        self.cam.log(
            f"Video recording started: "
            f"{self.base_name}"
        )

        self.cam.log(
            f"Temp folder: {self.temp_dir}"
        )

    # -------------------------------------------------

    def stop(self):

        if not self.is_recording:
            return

        self._flush_chunk()

        self._build_final_npz()

        duration = 0

        if (
            self.first_timestamp is not None
            and
            self.last_timestamp is not None
        ):
            duration = (
                self.last_timestamp
                - self.first_timestamp
            )

        fps = 0

        if duration > 0:
            fps = self.frame_count / duration

        self.is_recording = False

        self.cam.state.is_video_recording = False

        self.cam.emit_event(
            CameraEvent.VIDEO_REC_STOPPED
        )

        self.cam.log(
            f"Video recording stopped "
            f"({self.frame_count} frames) "
            f"in {duration:.1f}s "
            f"({fps:.2f} FPS)"
        )

    # -------------------------------------------------

    def process_frame(self, display_frame=None):

        if not self.is_recording:
            return

        timestamp = time.time()

        if self.first_timestamp is None:
            self.first_timestamp = timestamp

        self.last_timestamp = timestamp

        self.raw_frames.append(
            self.cam.thermal_frame.copy()
        )

        self.raw_timestamps.append(
            timestamp
        )

        self.frame_count += 1

        if self.frame_count % 25 == 0:

            self.cam.log(
                f"Recorded "
                f"{self.frame_count} frames"
            )

        if len(self.raw_frames) >= self.CHUNK_SIZE:
            self._flush_chunk()

    # -------------------------------------------------

    def _flush_chunk(self):

        if not self.raw_frames:
            return

        filename = (
            self.temp_dir /
            f"chunk_{self.chunk_index:05d}.npz"
        )

        np.savez_compressed(
            filename,
            thermal_frames=np.array(
                self.raw_frames,
                dtype=np.uint8
            ),
            timestamps=np.array(
                self.raw_timestamps,
                dtype=np.float64
            )
        )

        self.cam.log(
            f"Saved chunk "
            f"{self.chunk_index}"
        )

        self.chunk_index += 1

        self.raw_frames.clear()
        self.raw_timestamps.clear()

    # -------------------------------------------------

    def _build_final_npz(self):

        chunks = sorted(
            self.temp_dir.glob(
                "chunk_*.npz"
            )
        )

        if not chunks:
            return

        frames = []
        timestamps = []

        for chunk in chunks:

            data = np.load(
                chunk,
                allow_pickle=True
            )

            frames.append(
                data["thermal_frames"]
            )

            timestamps.append(
                data["timestamps"]
            )

        frames = np.concatenate(
            frames,
            axis=0
        )

        timestamps = np.concatenate(
            timestamps,
            axis=0
        )

        output_file = (
            f"{self.base_name}_raw.npz"
        )

        np.savez_compressed(
            output_file,
            thermal_frames=frames,
            timestamps=timestamps
        )

        self.cam.log(
            f"Raw recording saved: "
            f"{output_file}"
        )

        shutil.rmtree(
            self.temp_dir,
            ignore_errors=True
        )

        self.temp_dir = None

# # class_hikvideo_recorder.py

# import cv2
# import time
# import numpy as np
# from pathlib import Path
# from datetime import datetime

# from class_hikmodels import *

# class VideoRecorder:

#     def __init__(self, camera):
#         self.cam = camera
#         self.is_recording = False
#         self.display_writer = None
#         self.report_writer = None
#         self.first_timestamp = None
#         self.last_timestamp = None
#         self.raw_frames = []
#         self.raw_timestamps = []
#         self.frame_count = 0
#         self.output_folder = Path(".")

#     # -------------------------------------------------
#     # Recording control
#     # -------------------------------------------------

#     def start(self):
#         if self.is_recording:
#             return
#         settings = self.cam.video_settings
#         stamp = ""
#         if settings.append_timestamp:
#             stamp = datetime.now().strftime("_%Y%m%d_%H%M%S")

#         base_name = (settings.filename_prefix + stamp)
#         self.base_name = base_name
#         self.start_time = time.time()
#         self.frame_count = 0
#         self.raw_frames.clear()
#         self.raw_timestamps.clear()

#         self.display_writer = None
#         self.report_writer = None
#         self.is_recording = True
#         self.cam.state.is_video_recording = True
#         self.cam.emit_event(CameraEvent.VIDEO_REC_STARTED)
#         self.cam.log(
#             f"Video recording started: {self.base_name}")

#     # -------------------------------------------------

#     def stop(self):
#         if not self.is_recording:
#             return
#         if self.display_writer:
#             self.display_writer.release()

#         if self.report_writer:
#             self.report_writer.release()

#         self._save_raw()
#         duration = (self.last_timestamp - self.first_timestamp)
#         fps = self.frame_count / duration

#         self.display_writer = None
#         self.report_writer = None
#         self.is_recording = False
#         self.cam.state.is_video_recording = False
#         self.cam.emit_event(CameraEvent.VIDEO_REC_STOPPED)

#         self.cam.log(
#             f"Video recording stopped "
#             f"({self.frame_count} frames) " 
#             f"in {duration:.1f}s "
#             f"({fps:.2f} FPS)"
#         )
#     # -------------------------------------------------

#     def process_frame(self, display_frame):
#         if not self.is_recording:
#             return
        

#         if self.frame_count % 25 == 0:
#             self.cam.log(
#                 f"Recorded {self.frame_count} frames"
#             )

#         settings = self.cam.video_settings
#         timestamp = time.time()
#         if self.first_timestamp is None:
#             self.first_timestamp = timestamp
#         self.last_timestamp = timestamp

#         # ---------------------------------------------
#         # RAW recording
#         # ---------------------------------------------
#         # if settings.record_raw:
#         self.raw_frames.append(
#             self.cam.thermal_frame.astype(np.float32).copy())
#         self.raw_timestamps.append(timestamp)

#         # # ---------------------------------------------
#         # # DISPLAY recording
#         # # ---------------------------------------------
#         # if settings.record_display:
#         #     self._write_display(display_frame)

#         # # ---------------------------------------------
#         # # REPORT recording
#         # # ---------------------------------------------
#         # if settings.record_report:
#         #     report = self.cam.create_camera_report_frame(display_frame)
#         #     self._write_report(report)

#         self.frame_count += 1

#     # -------------------------------------------------

#     def _write_display(self, frame):
#         if self.display_writer is None:
#             settings = self.cam.video_settings
#             h, w = frame.shape[:2]
#             filename = f"{self.base_name}_display.mp4"
#             fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#             self.display_writer = cv2.VideoWriter(
#                 filename,
#                 fourcc,
#                 settings.fps,
#                 (w, h)
#             )
#         self.display_writer.write(frame)

#     # -------------------------------------------------

#     def _write_report(self, frame):
#         if self.report_writer is None:
#             h, w = frame.shape[:2]
#             filename = f"{self.base_name}_report.mp4"
#             fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#             self.report_writer = cv2.VideoWriter(
#                 filename,
#                 fourcc,
#                 25,
#                 (w, h)
#             )
#         self.report_writer.write(frame)

#     # -------------------------------------------------

#     def _save_raw(self):
#         # settings = self.cam.video_settings
#         if (not self.raw_frames):
#             return
#         filename = (f"{self.base_name}_raw.npz")
#         np.savez_compressed(
#             filename,
#             temperature_maps=np.array(
#                 self.raw_frames, dtype=np.float32),
#             timestamps=np.array(
#                 self.raw_timestamps, dtype=np.float64)
#         )
#         self.cam.log(f"Raw recording saved: {filename}")
