# class_hikvideo_exporter.py

import cv2
import numpy as np
from datetime import datetime

class VideoExporter:

    def __init__(self, camera, video_settings=None):
        self.cam = camera
        if video_settings is None:
            video_settings=self.cam.video_settings.video_export
        self.video_settings=video_settings

    def export_npz_to_mp4(
            self,
            npz_file,
            output_file,
            report=True):

        saved_thermal = self.cam.thermal_frame
        saved_metadata = self.cam.metadata_frame
        saved_lock = self.cam.lock_acquisition

        writer = None

        try:
            self.cam.lock_acquisition = True
            data = np.load(
                npz_file,
                allow_pickle=True
            )

            thermal_frames = data["thermal_frames"]
            timestamps = data["timestamps"]
            if len(thermal_frames) == 0:
                raise RuntimeError("No recorded frames")

            duration = (timestamps[-1] - timestamps[0])
            actual_fps = (
                len(thermal_frames) / duration if duration > 0 else 1.0)

            settings = self.video_settings
            export_fps = settings.fps

            if export_fps <= 0:
                export_fps = actual_fps

            total_frames = len(thermal_frames)
            self.cam.log(
                f"Exporting {total_frames} frames "
                f"({actual_fps:.2f} FPS recorded)"
            )
            for i, (th_frame,tstamp) in enumerate(zip(thermal_frames,timestamps)):
                # Replay frame
                self.cam.thermal_frame = (th_frame.copy())
                display = (
                    self.cam.create_display_frame_from_current(
                        self.cam.view_settings.display_width,
                        self.cam.view_settings.display_height
                    )
                )

                if report:
                    dt = datetime.fromtimestamp(tstamp)
                    ddate = dt.strftime("%Y-%m-%d")
                    dtime = dt.strftime("%H:%M:%S")
                    frame = self.cam.create_camera_report_frame(display, ddate, dtime)
                    
                else:
                    frame = display

                if writer is None:
                    h, w = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(
                        *"mp4v"
                    )
                    writer = cv2.VideoWriter(
                        output_file,
                        fourcc,
                        export_fps,
                        (w, h)
                    )

                    if not writer.isOpened():
                        raise RuntimeError(
                            f"Cannot open video writer: "
                            f"{output_file}"
                        )
                    self.cam.log(
                        f"Video size: "
                        f"{w}x{h}"
                        )
                writer.write(frame)

                if i % 100 == 0:
                    self.cam.log(
                        f"Export frame "
                        f"{i}/{total_frames}"
                    )

            self.cam.log(
                f"Export complete\n"
                f"Frames       : {total_frames}\n"
                f"Recorded FPS : {actual_fps:.2f}\n"
                f"Export FPS   : {export_fps:.2f}\n"
                f"Output       : {output_file}"
            )

        finally:

            if writer is not None:
                writer.release()

            self.cam.thermal_frame = saved_thermal
            self.cam.metadata_frame = saved_metadata
            self.cam.lock_acquisition = saved_lock