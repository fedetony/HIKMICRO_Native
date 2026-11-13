import platform
import subprocess
import re
import glob
import numpy as np
import os
import sys
import shlex
# os.environ["OPENCV_VIDEOIO_DEBUG"] = "1"
# os.environ["OPENCV_LOG_LEVEL"] = "DEBUG"
import cv2

import time
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from copy import copy
from collections import deque
from datetime import datetime
import csv

from class_hikconf_manager import HIKConfigurationManager
from class_hikmodels import *
from class_hikvideo_recorder import *
from class_hikvideo_exporter import *

class HIKMICRO_NATIVE:
    """
    Native HikMicro thermal camera interface.

    Provides:

    - Frame acquisition
    - Thermal analysis
    - Probe management
    - Calibration
    - Visualization
    - Event notifications

    The engine is GUI independent and can be
    integrated with OpenCV, Qt, logging systems,
    network interfaces, or custom applications.
    """
    VERSION = "1.0.0"
    # --------------------
    # Native thermal image
    # --------------------
    THERMAL_W = 256
    THERMAL_H = 192
    # --------------------
    # Raw native frame
    # (includes 4 metadata rows)
    # --------------------
    RAW_W = 256
    RAW_H = 196
    METADATA_ROWS = 4
    # --------------------
    # Default display size
    # --------------------
    DISPLAY_W = 800
    DISPLAY_H = 600
    # --------------------
    # Zoom limits
    # --------------------
    MIN_ZOOM = 1.0
    MAX_ZOOM = 16.0
    # --------------------
    # Probe limits
    # --------------------
    MIN_PROBE_SIZE = 2

    def __init__(self, camera_index=None, log_callback=None, thermal_modes:list[tuple]=None):
        """Set Camera index to point to a specific camera. 
        Note: If you use a diffferent camera set the viewport settings accordingly.

        Args:
            camera_index (int, optional): Set None to find HIKMICRO camera. Set your own Camera index for other cameras. 
            Set Camera index to -1 for virtual camera operation. Defaults to None.
            log_callback (callable, optional): Connect here your logger as a print function. Defaults to None (use print).
            thermal_modes (list(tuple),optional): Set different Raw native frame and camera modes for detection. 
                    Default None sets HIKMICRO: thermal_modes = [
                                (256, 196), -> first tuple selected as raw (RAW_H,RAW_W)
                                (256, 344),
                                (256, 360),
                                (256, 192), -> last tuple selected as (THERMAL_W, THERMAL_H)
                            ]

        Raises:
            RuntimeError: No camera Found
        """
        self.log = (log_callback if log_callback else print)
        self.view_settings = ViewSettings()
        self.viewport = Viewport()
        self.calibration = CalibrationSettings()
        
        self.txt_sett_cursor = TempTextSettings(
            font_scale=0.45,
            color=(255,255,255)
        )
        self.txt_sett_hot = TempTextSettings(
            font_scale=0.55,
            color=(255,0,255)
        )
        self.txt_sett_cold = TempTextSettings(
            font_scale=0.55,
            color=(255,255,0)
        )
        self.txt_sett_probe = TempTextSettings(
            font_scale=0.40,
            color=(255,255,255)
        )
        self.txt_sett_mask = TempTextSettings(
            font_scale=0.40,
            color=(0,255,255)
        )
        self.txt_sett_ruler = TempTextSettings(
            font_scale=0.45,
            color=(255,255,255)
        )
        self.txt_sett_scale = TempTextSettings(
            font_scale=0.45,
            color=(255,255,255)
        )
        # events
        self.event_callback = None
        self.state = EngineState()
        self.event_history = []
        self.emit_frame_ready_events = False
        
        # data Logging
        self.logging_settings = LoggingSettings()
        self.last_log_time = 0
        self.log_start_time = 0
        self.is_logging = False
        self.log_file = None

        # video settings
        self.video_settings = VideoSettings()
        self.is_video_recording = False
        self.lock_acquisition = False
        
        # temperature callback for calibration
        self.temperature_callback = None
        # Trackers
        self.mouse_x = 0
        self.mouse_y = 0
        self.cursor_tx = 0
        self.cursor_ty = 0

        self.is_drawing_probe = False
        self.is_drawing_mask = False
        self.drag_mode = None

        self.probe_start_x = 0
        self.probe_start_y = 0
        self.probe_current_x = 0
        self.probe_current_y = 0

        self.mask_start_x = 0
        self.mask_start_y = 0
        self.mask_current_x = 0
        self.mask_current_y = 0

        self.show_grid = self.view_settings.show_grid
        self.show_hotspot = self.view_settings.show_hotspot
        self.show_coldspot = self.view_settings.show_coldspot
        self.show_probes = self.view_settings.show_probes
        self.show_masks = self.view_settings.show_masks
        self.show_center_cross=self.view_settings.show_center_cross
        self.show_probe_labels = self.view_settings.show_probe_labels
        self.show_cursor = self.view_settings.show_cursor

        self.probes = {}
        self.next_probe_id = 1
        self.masks = {}
        self.next_mask_id = 1
        
        self.view_settings.zoom = 1.0
        self.raw_frame = None
        self.thermal_frame = None
        self.metadata_frame = None
        self.last_metadata_frame = None
        self.do_metadata_compare = False
        self.analysis = None

        self.cap = None
        if thermal_modes is None:
            # Thermal camera signatures
            self.thermal_modes = [
                (256, 196),
                (256, 344),
                (256, 360),
                (256, 192),
            ]
        else:
            self.thermal_modes = thermal_modes
            if not isinstance(thermal_modes,list):
                raise TypeError("Wrong thermal mode values")
            (self.RAW_W, self.RAW_H) = thermal_modes[0]
            (self.THERMAL_W, self.THERMAL_H) = thermal_modes[-1]
            self.METADATA_ROWS = abs(self.RAW_H-self.THERMAL_H)

        if camera_index is None:
            camera_index = self.find_correct_camera()

        if camera_index is None:
            raise RuntimeError("No camera found")

        self.camera_index = camera_index
        self.is_virtual_camera = False
        if self.camera_index != -1:
            self.open_camera()
        else:
            self.log("Virtual camera mode Active")
            self.is_virtual_camera = False
            self.lock_acquisition = True

        self.log(
            f"Using thermal camera "
            f"index {self.camera_index}"
        )
        self.configuration_manager=HIKConfigurationManager()
        self.video_recorder = VideoRecorder(self)
        self.video_exporter = VideoExporter(self)
        self.default_config="hik_default_config.json"
        self.load_config(self.default_config)   

    def set_emit_frame_ready_events(self,enable:bool):
        self.emit_frame_ready_events = enable     
    
    def export_video(self, npz_file, output_file):
        record_report=self.video_settings.video_export.record_report
        self.video_exporter.export_npz_to_mp4(
            npz_file,output_file,record_report)
    
    def meta_frame_analysis(self):
        if not self.do_metadata_compare:
            return
        if (self.metadata_frame is not None 
            and self.last_metadata_frame is not None):
            self.compare_metadata(self.last_metadata_frame,
                                  self.metadata_frame)
        
            
    def compare_metadata(self, old_meta, new_meta):
        diff = np.where(old_meta != new_meta)

        if len(diff[0]):
            print(f"{len(diff[0])} metadata bytes changed")

            for r, c in zip(*diff):
                print(
                    f"[{r},{c}] "
                    f"{old_meta[r,c]} -> {new_meta[r,c]}"
                )
    
    def load_config(self,filename):
        if not filename:
            return
        try:
            self.configuration_manager.load(filename)
            self.configuration_manager.apply(self)
            self.log(f"Loaded configuration {filename}")
        except Exception as eee:
            self.log(f"Error Loading {filename}: {eee}")
    
    def save_config(self, filename):
        if not filename:
            return
        try:
            self.configuration_manager.export_camera(self)
            self.configuration_manager.save(filename)
            self.log(f"Saved configuration {filename}")
        except Exception as ex:
            self.log(f"Error Saving {filename}: {ex}")
    
    def get_timestamped_filename(self, filename):

        stem = Path(filename).stem
        suffix = Path(filename).suffix

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        return f"{stem}_{timestamp}{suffix}"
    
    def find_correct_camera(self):

        if platform.system() == "Windows":
            return self.find_windows_camera()

        if platform.system() == "Linux":
            return self.find_linux_camera()

        return None


    def find_linux_camera(self):
        candidates = []

        devices = sorted(
            glob.glob("/dev/video*"),
            key=lambda x: int(x.replace("/dev/video", ""))
        )

        for device in devices:
            try:
                result = subprocess.run(
                    [
                        "v4l2-ctl",
                        "-d", device,
                        "--list-formats-ext"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                output = result.stdout

                # Only accept YUYV devices
                if "'YUYV'" not in output:
                    continue

                # Extract supported resolutions
                resolutions = re.findall(
                    r"Size:\s+Discrete\s+(\d+)x(\d+)",
                    output
                )

                supported = [
                    (int(w), int(h))
                    for w, h in resolutions
                ]

                matches = [
                    mode for mode in self.thermal_modes
                    if mode in supported
                ]

                if not matches:
                    continue

                # Verify OpenCV can open the device
                cap = cv2.VideoCapture(
                    device,
                    cv2.CAP_V4L2
                )

                if not cap.isOpened():
                    cap.release()
                    continue

                candidates.append({
                    "device": device,
                    "matches": matches,
                    "supported": supported
                })

                cap.release()

            except (subprocess.TimeoutExpired,
                    FileNotFoundError):
                continue

        if not candidates:
            self.log("No compatible thermal camera found")
            return None

        # Prefer devices supporting the distinctive thermal modes
        candidates.sort(
            key=lambda c: (
                (self.RAW_W, self.RAW_H) in c["matches"],
                (self.RAW_W, 344) in c["matches"],
                len(c["matches"])
            ),
            reverse=True
        )

        selected = candidates[0]
        self.log(f"Thermal camera found: {selected['device']}")
        self.log(f"Supported thermal modes: {selected['matches']}")

        return selected["device"]

    def find_windows_camera(self):
        candidates = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
            if not cap.isOpened():
                continue
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                self.log(f"Camera {i}: {w}x{h}")
                candidates.append((i, w, h))
            cap.release()   
        if not candidates:
            self.log("No compatible thermal camera found with CAP_MSMF trying CAP_DSHOW")
            for i in range(10):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    continue
                ret, frame = cap.read()
                if ret:
                    h, w = frame.shape[:2]
                    self.log(f"Camera {i}: {w}x{h}")
                    candidates.append((i, w, h))
                cap.release()      
        if not candidates:
            self.log("""Windows Camera Permissions:
Ensure Windows camera access is enabled under Settings → Privacy & security → Camera, 
including Let desktop apps access your camera. Also ensure Windows Camera Frame Server
is not disabled. Otherwise, OpenCV may fail to detect or open cameras (MSMF/DirectShow).""")
            self.log("No compatible thermal camera found")
            return None

        for i, w, h in candidates:
            if (w, h) != (640, 480):
                return i
        return candidates[0][0]    
  
    def open_camera(self):
        system = platform.system()
        if system == "Windows":
            
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)

            self.cap.set(cv2.CAP_PROP_FOURCC, 
                cv2.VideoWriter_fourcc(*"YUY2"))
        elif system == "Linux":
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)

            self.cap.set(cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*"YUYV")
            )
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.RAW_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.RAW_H)

        if not self.cap.isOpened():
            raise RuntimeError("Cannot open thermal camera")

        return self.cap

    #--------------------
    # Release
    #--------------------
    def release(self):
        if self.cap is not None:
            self.cap.release()

    def __del__(self):
        try:
            self.release()

        except Exception:
            pass
    
    #--------------------
    # Frame Aquisition
    #--------------------

    def acquire(self):
        if self.lock_acquisition:
            return self.thermal_frame
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Cannot read frame")
        # Windows MSMF
        if frame.shape == (1, self.RAW_H * self.RAW_W * 2):
            frame = frame.reshape(self.RAW_H, self.RAW_W, 2)

        # Linux V4L2
        elif frame.shape == (self.RAW_H, self.RAW_W, 2):
            pass

        else:
            raise RuntimeError(
                f"Unknown native frame shape: {frame.shape}")

        self.raw_frame = frame
        self.thermal_frame = frame[0:self.THERMAL_H,:,0].copy()
        self.last_metadata_frame = self.metadata_frame
        self.metadata_frame = frame[self.THERMAL_H:self.RAW_H,:,0].copy()
        self.meta_frame_analysis()

        self.state.frame_ready = True
        if self.emit_frame_ready_events:
            self.emit_event(CameraEvent.FRAME_READY)

        return self.thermal_frame
    
    def get_temperature_map(self):
        if self.thermal_frame is None:
            self.acquire()
        return self.thermal_frame.astype(np.float32)
    
    def check_mask_mode(self,mode):
        if isinstance(mode,MaskMode):
            return mode
        
        for a_mode in MaskMode:
            if mode.lower() == a_mode.value:
                return a_mode 
        return mode
    
    def check_temp_mode(self,mode):
        if isinstance(mode,TempMode):
            return mode
        
        for a_mode in TempMode:
            if mode.lower() == a_mode.value:
                return a_mode 
        return mode
    
    def get_analysis_temperature_map(self):
        temp_map = self.get_temperature_map().copy()
        global_min = np.min(temp_map)
        global_max = np.max(temp_map)

        for mask in self.masks.values():
            if not mask.enabled:
                continue
            roi = temp_map[mask.y1:mask.y2, mask.x1:mask.x2]
            if roi.size == 0:
                continue
            mmode=self.check_mask_mode(mask.mode)
            mask.mode = mmode
            if mmode == MaskMode.CONSTANT:
                value = max(0, min(255, int(mask.raw_value)))
                roi[:] = value

            elif mmode == MaskMode.MINIMUM:
                roi[:] = global_min

            elif mmode == MaskMode.MAXIMUM:
                roi[:] = global_max

            elif mmode == MaskMode.EXCLUDE:
                # Neutral value
                roi[:] = 128
            
            elif mmode == MaskMode.NORMALIZED:
                roi_min = np.min(roi)
                roi_max = np.max(roi)
                if roi_max > roi_min:
                    roi[:] = np.interp(
                        roi,
                        [roi_min, roi_max],
                        [mask.normalize_min, mask.normalize_max]
                    ).astype(np.uint8)

                else:
                    roi[:] = mask.normalize_min
            else:
                pass

        return temp_map
    
    def save_native_debug(self):
        self.acquire()
        cv2.imwrite("thermal_native.png", self.thermal_frame)
        big = cv2.resize(self.metadata_frame, (1024, 200), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite("metadata_rows.png", big)
        inferno = cv2.applyColorMap(self.thermal_frame, cv2.COLORMAP_INFERNO)
        cv2.imwrite("thermal_inferno.png", inferno)
        meta_color = cv2.applyColorMap(big, cv2.COLORMAP_TURBO)
        cv2.imwrite("metadata_rows_turbo.png",meta_color)
        np.save("metadata_frame.npy",self.metadata_frame)
        self.log("Saved native debug files")
    
    #--------------------
    # Temperature Analysis
    #--------------------
    def analyze_frame(self)->ThermalFrameAnalysis:
        temp_map = self.get_analysis_temperature_map()

        blur = cv2.GaussianBlur(temp_map, (5, 5), 0)
        hot_y, hot_x = np.unravel_index(np.argmax(blur), blur.shape)
        cold_y, cold_x = np.unravel_index(np.argmin(blur), blur.shape)

        analysis = ThermalFrameAnalysis(

            timestamp=time.time(),

            hotspot_x=int(hot_x),
            hotspot_y=int(hot_y),
            hotspot_value=float(blur[hot_y, hot_x]),

            coldspot_x=int(cold_x),
            coldspot_y=int(cold_y),
            coldspot_value=float(blur[cold_y, cold_x]),

            average_value=float(np.mean(temp_map)),
            minimum_value=float(np.min(temp_map)),
            maximum_value=float(np.max(temp_map)),
            frame_width=temp_map.shape[1],
            frame_height=temp_map.shape[0]
        )

        self.analysis = analysis
        return analysis
    
    def hotspot(self)->TemperaturePoint:

        if self.analysis is None:
            self.analyze_frame()

        return TemperaturePoint(
            self.analysis.hotspot_x,
            self.analysis.hotspot_y,
            self.analysis.hotspot_value
        )
    
    def coldspot(self)->TemperaturePoint:
        if self.analysis is None:
            self.analyze_frame()

        return TemperaturePoint(
            self.analysis.coldspot_x,
            self.analysis.coldspot_y,
            self.analysis.coldspot_value
        )
    
    def measure_area(self, center_x, center_y, radius=0)->ROIStats:
        temp_map = self.get_analysis_temperature_map()
        x1 = max(0, center_x - radius)
        y1 = max(0, center_y - radius)
        x2 = min(temp_map.shape[1], center_x + radius + 1)
        y2 = min(temp_map.shape[0], center_y + radius + 1)

        roi = temp_map[y1:y2, x1:x2]
        return ROIStats(
            minimum=float(np.min(roi)),
            maximum=float(np.max(roi)),
            average=float(np.mean(roi)),
            stddev=float(np.std(roi))
        )
    
    #--------------------
    # Interface Functions
    #--------------------
    def get_cursor_temperature(self, display_x, display_y, radius=2):
        tx, ty = self.display_to_temperature(
            display_x,
            display_y,
            self.view_settings.display_width,
            self.view_settings.display_height
        )
        stats = self.measure_area(tx, ty, radius)
        return tx, ty, stats

    def begin_mask(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (not self.show_masks
            or self.is_video_recording 
            or self.is_logging):
                return
        vs = self.view_settings
        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)
        self.is_drawing_mask = True
        self.mask_start_x = tx
        self.mask_start_y = ty
        self.mask_current_x = tx
        self.mask_current_y = ty
    
    def creating_mask(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        vs = self.view_settings
        self.cursor_tx, self.cursor_ty = (
                self.display_to_temperature(x, y, vs.display_width, vs.display_height))
        if self.is_drawing_mask:
            self.mask_current_x, self.mask_current_y = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)
    
    def finish_mask(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (not self.show_masks
            or self.is_video_recording 
            or self.is_logging):
                return
        vs = self.view_settings
        self.is_drawing_probe = False
        self.is_drawing_mask = False
        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)
        
        x1 = min(self.mask_start_x, tx)
        x2 = max(self.mask_start_x, tx)
        y1 = min(self.mask_start_y, ty)
        y2 = max(self.mask_start_y,ty)
        if (x2 - x1) < self.MIN_PROBE_SIZE:
            x2 = min(self.THERMAL_W, x1 + self.MIN_PROBE_SIZE)
        if (y2 - y1) < self.MIN_PROBE_SIZE:
            y2 = min(self.THERMAL_H, y1 + self.MIN_PROBE_SIZE)
        name = f"MASK{self.next_mask_id}"
        self.next_mask_id += 1
        self.add_mask(name, x1, y1, x2, y2)
        self.log(f"Added {name} ({x1},{y1}) -> ({x2},{y2})")
    
    def removing_mask(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (self.is_logging
            or self.is_video_recording):
            return
        nearest = None
        best_dist = 999999
        vs = self.view_settings
        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)

        for mask in self.masks.values():
            px = (mask.x1 + mask.x2) // 2
            py = (mask.y1 + mask.y2) // 2

            dist = ((px-tx)**2 + (py-ty)**2)

            if dist < best_dist:
                best_dist = dist
                nearest = mask.name

        if nearest:
            self.remove_mask(nearest)
            self.log(f"Removed {nearest}")
    
    def begin_probe(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (not self.show_probes
            or self.is_video_recording 
            or self.is_logging):
            return
        vs = self.view_settings
        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)

        self.is_drawing_probe = True

        self.probe_start_x = tx
        self.probe_start_y = ty

        self.probe_current_x = tx
        self.probe_current_y = ty
        
    def creating_probe(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        vs = self.view_settings
        self.cursor_tx, self.cursor_ty = (
                self.display_to_temperature(x, y, vs.display_width, vs.display_height))
        if self.is_drawing_probe:
            self.probe_current_x, self.probe_current_y = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)
        
    def finish_probe(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (not self.is_drawing_probe
            or self.is_video_recording 
            or self.is_logging):
            return
        vs = self.view_settings
        self.is_drawing_probe = False
        self.is_drawing_mask = False
        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)
        
        x1 = min(self.probe_start_x, tx)
        x2 = max(self.probe_start_x, tx)
        y1 = min(self.probe_start_y, ty)
        y2 = max(self.probe_start_y,ty)
        if (x2 - x1) < self.MIN_PROBE_SIZE:
            x2 = min(self.THERMAL_W, x1 + self.MIN_PROBE_SIZE)
        if (y2 - y1) < self.MIN_PROBE_SIZE:
            y2 = min(self.THERMAL_H, y1 + self.MIN_PROBE_SIZE)
        name = f"P{self.next_probe_id}"
        self.next_probe_id += 1
        self.add_probe(name, x1, y1, x2, y2)
        self.log(f"Added {name} ({x1},{y1}) -> ({x2},{y2})")
        
    def removing_probe(self,x,y):
        self.mouse_x = x
        self.mouse_y = y
        if (self.is_logging
            or self.is_video_recording):
            return
        vs = self.view_settings
        nearest = None
        best_dist = 999999

        tx, ty = self.display_to_temperature(
                x, y, vs.display_width, vs.display_height)

        for probe in self.probes.values():
            px = (probe.x1 + probe.x2) // 2
            py = (probe.y1 + probe.y2) // 2

            dist = ((px-tx)**2 + (py-ty)**2)

            if dist < best_dist:
                best_dist = dist
                nearest = probe.name

        if nearest:
            self.remove_probe(nearest)
            self.log(f"Removed {nearest}")
    
    def mousewheeling(self,x,y,flags):
        self.mouse_x = x
        self.mouse_y = y
        if (self.is_logging 
            or self.is_video_recording):
            return
        # Update zoom center
        vs = self.view_settings
        # vs.center_x = self.cursor_tx
        # vs.center_y = self.cursor_ty
        tx, ty = self.display_to_temperature(
            x, y, vs.display_width, vs.display_height)
        vs.center_x = tx
        vs.center_y = ty

        if flags > 0:
            self.set_zoom(self.view_settings.zoom * 1.2)
        else:
            self.set_zoom(self.view_settings.zoom / 1.2)
                
    def mouse_callback(self, event, x, y, flags, param):
        self.mouse_x = x
        self.mouse_y = y
        
        ctrl  = bool(flags & cv2.EVENT_FLAG_CTRLKEY)
        shift = bool(flags & cv2.EVENT_FLAG_SHIFTKEY)

        # Mask
        if (event == cv2.EVENT_LBUTTONDOWN and
            shift):
            self.drag_mode = "MASK"
            self.begin_mask(x,y)

        elif (event == cv2.EVENT_MOUSEMOVE and
            shift):
            self.creating_mask(x,y)
                
        elif (event == cv2.EVENT_LBUTTONUP and
            shift):
            self._finish_drag_mode(x,y)

        # Remove nearest mask
        elif (event == cv2.EVENT_RBUTTONDOWN and
            shift):
            self.removing_mask(x,y)
        
        # Add probe
        elif (event == cv2.EVENT_LBUTTONDOWN and
              ctrl):
            self.drag_mode = "PROBE"
            self.begin_probe(x,y)
        
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drag_mode == "MASK":
                self.creating_mask(x,y)

            elif self.drag_mode == "PROBE":
                self.creating_probe(x,y)
        
        elif (event == cv2.EVENT_LBUTTONUP and
            ctrl):
            self._finish_drag_mode(x,y)

        elif event == cv2.EVENT_LBUTTONUP:
            self._finish_drag_mode(x,y)

        # Remove nearest probe
        elif (event == cv2.EVENT_RBUTTONDOWN and
              ctrl):
            self.removing_probe(x,y)
        
        elif event == cv2.EVENT_MOUSEWHEEL:
            self.mousewheeling(x,y,flags)
    
    def _finish_drag_mode(self,x,y):
        if self.drag_mode == "MASK":
            self.finish_mask(x,y)

        elif self.drag_mode == "PROBE":
            self.finish_probe(x,y)
        self.drag_mode = None
    
    def draw_center_cross(self, frame):
        h, w = frame.shape[:2]
        cx = w // 2
        cy = h // 2
        cv2.drawMarker(frame, (cx, cy), 
            (255,255,255), cv2.MARKER_CROSS, 15,1)
        return frame

    def draw_cursor_overlay(self, frame):
        tx, ty, stats = self.get_cursor_temperature(
            self.mouse_x, self.mouse_y,2)
        px = self.mouse_x
        py = self.mouse_y

        cv2.circle(
            frame,
            (px, py),
            4,
            self.txt_sett_cursor.color,
            1
        )
        mode = self.txt_sett_cursor.mode
        mode = self.check_temp_mode(mode)
        if  mode == TempMode.AVERAGE:
            value = stats.average
        elif mode == TempMode.MAXIMUM:
            value = stats.maximum
        elif mode == TempMode.MINIMUM:
            value = stats.minimum
        elif mode == TempMode.DEVIATION:
            value = stats.stddev
        else:
            value = stats.average
        self.draw_text(
            frame,
            f"{self.format_temperature(value,self.txt_sett_cursor)}",
            (px+6, py-6),
            self.txt_sett_cursor)
        return frame

    def draw_grid_overlay(self, frame, spacing=16):
        vp = self.viewport
        h, w = frame.shape[:2]
        start_x = (vp.x1 // spacing) * spacing
        for image_x in range(start_x, vp.x2 + spacing, spacing):
            screen_x = int((image_x - vp.x1) * w / (vp.x2 - vp.x1))
            cv2.line(
                frame,
                (screen_x, 0),
                (screen_x, h),
                (50, 50, 50),
                1
            )

        start_y = (vp.y1 // spacing) * spacing
        for image_y in range(start_y, vp.y2 + spacing, spacing):
            screen_y = int((image_y - vp.y1) * h / (vp.y2 - vp.y1))
            cv2.line(
                frame,
                (0, screen_y),
                (w, screen_y),
                (50, 50, 50),
                1)
        return frame
    
    def set_zoom(self, zoom):
        if (self.is_logging 
            or self.is_video_recording):
            return
        self.view_settings.zoom = max(1.0, min(zoom, 16.0))
        self.state.view_changed = True
        self.emit_event(CameraEvent.VIEW_CHANGED, self.view_settings)
    
    def draw_probe_creation_overlay(self, frame):
        if not self.is_drawing_probe:
            return frame
        h, w = frame.shape[:2]
        x1, y1 = self.temperature_to_display(
            self.probe_start_x, self.probe_start_y, w, h)
        x2, y2 = self.temperature_to_display(
            self.probe_current_x, self.probe_current_y, w, h)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,255), 1)
        return frame
    
    def draw_mask_creation_overlay(self, frame):
        if not self.is_drawing_mask:
            return frame
        h, w = frame.shape[:2]
        x1, y1 = self.temperature_to_display(
            self.mask_start_x, self.mask_start_y, w, h)
        x2, y2 = self.temperature_to_display(
            self.mask_current_x, self.mask_current_y, w, h)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,255), 1)
        return frame
    
    #--------------------
    # Masks
    #--------------------
    def add_mask(self, name, x1, y1, x2, y2)->ProbeArea:
        """Create a new thermal Mask.

        Parameters
        ----------
        name : str
            Unique mask name.

        x1, y1, x2, y2 : int
            Mask rectangle in thermal coordinates
            (256x192 sensor space).

        Returns
        -------
        MaskArea
            Newly created mask instance.

        Notes
        -----
        Emits CameraEvent.MASK_ADDED.
        """

        self.masks[name] = MaskArea(
            name=name,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            text_settings=copy(self.txt_sett_mask),
            color=self.txt_sett_mask.color
        )
        self.state.masks_changed = True
        self.emit_event(CameraEvent.MASK_ADDED, self.masks[name])
        return self.masks[name]
    
    def remove_mask(self, name):
        if name in self.masks:
            del self.masks[name]
            self.state.masks_changed = True
            self.emit_event(CameraEvent.MASK_REMOVED, name)
    
    def rename_mask(self,name,newname):
        if newname in self.masks:
            self.emit_event(CameraEvent.LOG_MESSAGE,f"Mask '{newname}' is not available")
            return
        if name in self.masks.keys():
            mask = self.masks[name]
            mask.name = newname
            self.remove_mask(name)
            self.masks[newname]=mask
            self.state.masks_changed = True
            self.emit_event(CameraEvent.MASK_ADDED, self.masks[newname])
    
    def get_mask(self, name)->MaskArea:
        return self.masks.get(name, None)
    
    def get_masks_infos(self):
        return {
            name: copy(mask.__dict__)
            for name, mask in self.masks.items()
        }
    #--------------------
    # Probes
    #--------------------

    def add_probe(self, name, x1, y1, x2, y2)->ProbeArea:
        """Create a new thermal probe.

        Parameters
        ----------
        name : str
            Unique probe name.

        x1, y1, x2, y2 : int
            Probe rectangle in thermal coordinates
            (256x192 sensor space).

        Returns
        -------
        ProbeArea
            Newly created probe instance.

        Notes
        -----
        Emits CameraEvent.PROBE_ADDED.
        """
        self.probes[name] = ProbeArea(
            name=name,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            history=[],
            text_settings=copy(self.txt_sett_probe)
        )
        self.state.probes_changed = True
        self.emit_event(CameraEvent.PROBE_ADDED, self.probes[name])
        return self.probes[name]

    def remove_probe(self, name):
        if name in self.probes:
            del self.probes[name]
            self.state.probes_changed = True
            self.emit_event(CameraEvent.PROBE_REMOVED, name)
    
    def rename_probe(self,name,newname):
        if newname in self.probes:
            self.emit_event(CameraEvent.LOG_MESSAGE,f"Probe '{newname}' is not available")
            return
        if name in self.probes.keys():
            probe = self.probes[name]
            probe.name = newname
            self.remove_probe(name)
            self.probes[newname]=probe
            self.state.probes_changed = True
            self.emit_event(CameraEvent.PROBE_ADDED, self.probes[newname])
    
    def get_probe(self, name)->ProbeArea:
        return self.probes.get(name, None)
    
    def get_probes_infos(self):
        return {
            name: copy(probe.__dict__)
            for name, probe in self.probes.items()
        }
    
    def analyze_probe(self, name,temp_map=None,timestamp=None):
        probe = self.get_probe(name)
        if probe is None:
            return None

        if temp_map is None:
            temp_map = self.get_analysis_temperature_map()

        roi = temp_map[probe.y1:probe.y2, probe.x1:probe.x2]

        if roi.size == 0:
            return probe

        min_val = float(np.min(roi))
        max_val = float(np.max(roi))
        avg_val = float(np.mean(roi))

        hot_y, hot_x = np.unravel_index(np.argmax(roi),roi.shape)
        cold_y, cold_x = np.unravel_index(np.argmin(roi), roi.shape)

        if timestamp is None:
            probe.timestamp = time.time()
        else:
            probe.timestamp = timestamp

        probe.minimum_temp = min_val
        probe.maximum_temp = max_val
        probe.average_temp = avg_val

        probe.hotspot_temp = max_val
        probe.coldspot_temp = min_val

        probe.hotspot_x = probe.x1 + int(hot_x)
        probe.hotspot_y = probe.y1 + int(hot_y)

        probe.coldspot_x = probe.x1 + int(cold_x)
        probe.coldspot_y = probe.y1 + int(cold_y)

        probe.history.append(
            (
                probe.timestamp,
                avg_val,
                min_val,
                max_val
            )
        )
        if (probe.high_alarm.enabled and
            probe.average_temp > probe.high_alarm.threshold):
            if not probe.high_alarm.active:
                probe.high_alarm.active = True
                trigger_settings = probe.high_alarm.trigger_settings
                trigger = (not trigger_settings.trigger_once
                    or trigger_settings.trigger_count == 0)
                if trigger and trigger_settings.enabled:
                    if not trigger_settings.trigger_once:
                        trigger_settings.trigger_count = 0
                    else:
                        trigger_settings.trigger_count += 1
                    self.execute_trigger(
                        trigger_settings,
                        probe,
                        "HIGH"
                    )
                self.emit_event(CameraEvent.ALARM_TRIGGERED_H,probe)
        elif (probe.high_alarm.enabled and
            probe.average_temp <= probe.high_alarm.threshold):
            if probe.high_alarm.active:
                probe.high_alarm.active = False
                self.emit_event(CameraEvent.ALARM_CLEARED_H,probe)
        self.state.alarm_triggered_h = self.has_high_alarms()

        if (probe.low_alarm.enabled and
            probe.average_temp < probe.low_alarm.threshold):
            if not probe.low_alarm.active:
                probe.low_alarm.active = True
                trigger_settings = probe.low_alarm.trigger_settings
                trigger = (not trigger_settings.trigger_once
                    or trigger_settings.trigger_count == 0)
                if trigger and trigger_settings.enabled:
                    if not trigger_settings.trigger_once:
                        trigger_settings.trigger_count = 0
                    else:
                        trigger_settings.trigger_count += 1
                    self.execute_trigger(
                        trigger_settings,
                        probe,
                        "LOW"
                    )
                self.emit_event(CameraEvent.ALARM_TRIGGERED_L,probe)
        elif (probe.low_alarm.enabled and
            probe.average_temp >= probe.low_alarm.threshold):
            if probe.low_alarm.active:
                probe.low_alarm.active = False
                self.emit_event(CameraEvent.ALARM_CLEARED_L,probe)
        self.state.alarm_triggered_l = self.has_low_alarms()    
        return probe
    
    def has_high_alarms(self):
        for probe in self.probes.values():
            if probe.high_alarm.active:
                return True
        return False
    
    def has_low_alarms(self):
        for probe in self.probes.values():
            if probe.low_alarm.active:
                return True

        return False

    def execute_trigger(
            self,
            trigger_settings: TriggerSettings,
            probe: ProbeArea = None,
            trigger_type: str = ""):

        if not trigger_settings.enabled:
            return False

        exe = str(trigger_settings.executable).strip()
        if not exe:
            return False
        try:

            payload = {
                "trigger_type": trigger_type,
                "probe_data": (
                    probe.to_data_dict()
                    if probe is not None
                    else {}
                ),
                "probe_config": (
                    probe.to_config_dict()
                    if probe is not None
                    else {}
                )
            }

            fd, json_file = tempfile.mkstemp(
                suffix=".json",
                prefix="hik_alarm_"
            )
            os.close(fd)

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, default=str)

            ext = os.path.splitext(exe)[1].lower()
            if ext == ".py":
                subprocess.Popen(
                [sys.executable, exe, json_file], start_new_session=True)

            elif ext == ".sh":
                subprocess.Popen(
                    ["bash", exe, json_file], start_new_session=True)

            elif ext in {".bat", ".cmd"}:
                subprocess.Popen(
                    f'"{exe}" "{json_file}"',
                    shell=True, start_new_session=True)
            else:
                subprocess.Popen(
                    [exe, json_file], start_new_session=True)

            self.log(f"Trigger executed: {exe}")
            self.log(f"Trigger json dumped in {json_file}")
            return True
        except Exception as ex:
            self.log(f"Trigger failed: {ex}")
            return False
    
    def analyze_all_probes(self):
        results = {}
        timestamp = time.time()
        temp_map = self.get_analysis_temperature_map()
        for name in self.probes:
            results[name] = self.analyze_probe(name,temp_map,timestamp)
        return results
    
    def clear_probe_history(self, name):
        probe = self.get_probe(name)
        if probe:
            probe.history.clear()
    
    def clear_all_probe_history(self):
        for probe in self.probes.values():
            probe.history.clear()
    
    #--------------------
    # Image
    #--------------------
    def create_colormapped_frame(self,temp_map=None, 
                                 colormap=ColorMap.INFERNO.value, 
                                 use_clahe=True, normalize=True):
        """thermal frame
            ↓
            normalize
            ↓
            CLAHE
            ↓
            colormap
            ↓
            RGB image
            """
        if temp_map is None:
            temp_map = self.get_analysis_temperature_map()
        # Normalize
        if normalize:
            normalized = cv2.normalize(temp_map, None, 0, 255, cv2.NORM_MINMAX)
            thermal_8bit = normalized.astype(np.uint8)
        else:
            thermal_8bit = temp_map.astype(np.uint8)
        # Optional CLAHE
        if use_clahe:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            thermal_8bit = clahe.apply(thermal_8bit)

        # Apply colormap
        colored = cv2.applyColorMap(thermal_8bit, colormap)
        return colored
    
    
    def snapshot(self,filename="colormapped.png"):
        frame = self.create_colormapped_frame(colormap=self.view_settings.colormap,
                                              use_clahe=self.view_settings.use_clahe)
        cv2.imwrite(filename, frame)
    
    def snapshot_report(self, filename):
        if not filename:
            return
        frame = self.create_display_frame(
            self.view_settings.display_width,
            self.view_settings.display_height
        )
        cv2.imwrite(filename, frame)
    
    def snapshot_raw(self, filename):
        if not filename:
            return
        frame = self.create_colormapped_frame(colormap=self.view_settings.colormap,
                                              use_clahe=self.view_settings.use_clahe)
        cv2.imwrite(filename, frame)
    
    def snapshot_sensor(self, filename):
        if not filename:
            return
        np.save(filename, self.get_temperature_map())
    
    def snapshot_camera_report(self,filename):
        if not filename:
            return
        # viewer image
        frame = self.create_display_frame(
                self.view_settings.display_width,
                self.view_settings.display_height
            )
        report = self.create_camera_report_frame(frame)
        cv2.imwrite(filename, report)

    def create_camera_report_frame(self, frame=None,ddate:str=None,dtime:str=None):
        if frame is None:
            frame = self.create_display_frame_from_current(
                self.view_settings.display_width,
                self.view_settings.display_height
            )
        h, w = frame.shape[:2]
        ruler_w = 50
        ruler_h = 50
        scale_w = 120
        scale_h = 80
        title_h = 30
        total_width = ruler_w + w + scale_w
        rs=self.video_settings.video_export.report
        # --------------------------------------------------
        # Center image
        # --------------------------------------------------
        center = frame
        # --------------------------------------------------
        # Rulers / scales
        # --------------------------------------------------
        left = self.create_pixel_ruler_vertical(
            display_height=h,
            width=ruler_w,
            spacing=self.view_settings.grid_spacing
        ) if self.view_settings.show_ruler_v else \
            np.zeros((h, ruler_w, 3), dtype=np.uint8)

        right = self.create_scale_bar(
            width=scale_w,
            height=h,
            vertical=True
        ) if self.view_settings.show_scale_bar_v else \
            np.zeros((h, scale_w, 3), dtype=np.uint8)

        top = self.create_pixel_ruler_horizontal(
            display_width=w,
            height=ruler_h,
            spacing=self.view_settings.grid_spacing
        ) if self.view_settings.show_ruler_h else \
            np.zeros((ruler_h, w, 3), dtype=np.uint8)

        bottom = self.create_scale_bar(
            width=w,
            height=scale_h,
            vertical=False
        ) if self.view_settings.show_scale_bar_h else \
            np.zeros((scale_h, w, 3), dtype=np.uint8)

        # --------------------------------------------------
        # Corner panels
        # --------------------------------------------------
        info = self.get_engine_info()
        if rs.show_version:
            tl_lines = [rs.company, self.VERSION]
        else:
            tl_lines = []
            
        tl = self.create_corner_panel(
            ruler_w,
            ruler_h,
            tl_lines
        )

        if rs.show_timestamp:
            tr_lines = [datetime.now().strftime("%Y-%m-%d") if ddate is None else ddate,
                        datetime.now().strftime("%H:%M:%S") if dtime is None else dtime]
        else:
            tr_lines = []

        tr = self.create_corner_panel(
            scale_w,
            ruler_h,
            tr_lines
        )

        bl = self.create_corner_panel(
            ruler_w,
            scale_h,
            [
                f"Zoom {info['zoom']:.2f}x",
                f"{self.THERMAL_W}x{self.THERMAL_H}"
            ]
        )

        if rs.show_statistics:
            cal_text = (
                self.calibration.calibration_type
                if self.calibration.enabled
                else "OFF")
            br_lines = [
                f"P:{info['probe_count']}",
                f"M:{info['mask_count']}",
                f"Cal:{cal_text}"
            ]
        else:
            br_lines = []
        br = self.create_corner_panel(scale_w, scale_h, br_lines)

        title = rs.title
        if rs.subtitle:
            title += f": {rs.subtitle}"
        title_row = self.create_corner_panel(
            total_width,title_h,
            [title]
        )
        # --------------------------------------------------
        # Assemble rows
        # --------------------------------------------------
        top_row = np.hstack([tl, top, tr])
        middle_row = np.hstack([left, center, right])
        bottom_row = np.hstack([bl, bottom, br])
        rows = []
        if rs.show_title and (rs.title or rs.subtitle):
            rows.append(title_row)
        rows.append(top_row)
        rows.append(middle_row)
        rows.append(bottom_row)
        report = np.vstack(rows)

        return report
    
    def create_corner_panel(self, width, height, lines):
        panel = np.zeros(
            (height, width, 3),
            dtype=np.uint8
        )
        y = 18
        for line in lines:
            self.draw_text(
                panel,
                line,
                (5, y),
                self.txt_sett_ruler
            )
            y += 16
        return panel
    
    def draw_mask_overlay(self, frame):
        h, w = frame.shape[:2]
        for mask in self.masks.values():
            if not isinstance(mask,MaskArea):
                continue
            if not mask.visible:
                continue
            x1, y1 = self.temperature_to_display(
                mask.x1, mask.y1, w, h)
            x2, y2 = self.temperature_to_display(
                mask.x2, mask.y2, w, h)
            cv2.rectangle(
                frame, (x1, y1), (x2, y2), mask.color, mask.line_thickness)
            self.draw_text(frame, mask.name,
                (x1, y1 - 3), mask.text_settings)
        return frame
    
    def draw_hotcold_overlay(self, frame, analysis=None):

        if analysis is None:
            analysis = self.analyze_frame()

        h, w = frame.shape[:2]

        hot_x, hot_y = self.temperature_to_display(
            analysis.hotspot_x,
            analysis.hotspot_y,
            w, h)

        cold_x, cold_y = self.temperature_to_display(
            analysis.coldspot_x,
            analysis.coldspot_y,
            w, h)

        # Hot marker
        if self.show_hotspot:
            cv2.drawMarker(frame,(hot_x, hot_y), 
                    self.txt_sett_hot.color, cv2.MARKER_CROSS, 12, 1)
            cv2.circle(frame, (hot_x, hot_y), 10, self.txt_sett_hot.color,1)
            self.draw_text(
                frame,
                f"H:{self.format_temperature(analysis.hotspot_value,self.txt_sett_hot)}",
                (hot_x + 8, hot_y - 5),
                self.txt_sett_hot)

        # Cold marker
        if self.show_coldspot:
            cv2.drawMarker(frame, (cold_x, cold_y),
                    self.txt_sett_cold.color, cv2.MARKER_TRIANGLE_DOWN, 12, 1)
            cv2.circle(frame, (cold_x, cold_y), 10, self.txt_sett_cold.color,1)
            self.draw_text(
                frame,
                f"C:{self.format_temperature(analysis.coldspot_value,self.txt_sett_cold)}",
                (cold_x + 8, cold_y - 5),
                self.txt_sett_cold)

        return frame
    
    def draw_probe_overlay(self, frame):
        h, w = frame.shape[:2]
        for probe in self.probes.values():
            if not isinstance(probe,ProbeArea):
                continue
            if not probe.visible:
                continue
            x1, y1 = self.temperature_to_display(probe.x1, probe.y1, w, h)
            x2, y2 = self.temperature_to_display(probe.x2, probe.y2, w, h)

            cv2.rectangle(frame, (x1, y1), (x2, y2), probe.color, probe.line_thickness)
            mode = probe.text_settings.mode
            mode = self.check_temp_mode(mode)
            if  mode == TempMode.AVERAGE:
                value = probe.average_temp
            elif mode == TempMode.MAXIMUM:
                value = probe.maximum_temp
            elif mode == TempMode.MINIMUM:
                value = probe.minimum_temp
            elif mode == TempMode.DEVIATION:
                value = probe.maximum_temp - probe.minimum_temp
            else:
                value = probe.average_temp
            label = f"{probe.name} {self.format_temperature(value,probe.text_settings)}"

            if self.show_probe_labels:
                self.draw_text(frame, label, (x1, max(10, y1 - 3)),
                    probe.text_settings)

            hx, hy = self.temperature_to_display(probe.hotspot_x, probe.hotspot_y, w, h)
            cx, cy = self.temperature_to_display(probe.coldspot_x, probe.coldspot_y, w, h)

            if probe.show_hotspot:
                cv2.drawMarker(frame, (hx, hy), (0,0,255), cv2.MARKER_CROSS, 8, 1)
            if probe.show_coldspot:    
                cv2.drawMarker(frame, (cx, cy), (255,255,0), cv2.MARKER_CROSS, 8, 1)
            
            # print("Probe:", probe.x1, probe.y1, probe.x2, probe.y2)

            # x1,y1 = self.temperature_to_display(probe.x1, probe.y1, w,h)
            # x2,y2 = self.temperature_to_display(probe.x2,probe.y2,w,h)

            # print("Display:", x1,y1,x2,y2)

        return frame
    
    def resize_display(self, frame, width, height):
        return cv2.resize(frame, (width, height), 
            interpolation=cv2.INTER_NEAREST)
    
    def create_display_frame_from_current(self, width=None, height=None):
        analysis = self.analyze_frame()
        self.analyze_all_probes()
        # Base image
        frame = self.create_colormapped_frame(
            colormap=self.view_settings.colormap,
            use_clahe=self.view_settings.use_clahe,
            normalize=True)
        # IMPORTANT:
        # establish viewport first
        frame = self.crop_zoom_frame(frame)
        # resize
        if width and height:
            frame = self.resize_display(frame, width, height)
        # Draw overlays AFTER zoom/crop/resize
        if self.show_hotspot or self.show_coldspot:
            frame = self.draw_hotcold_overlay(frame, analysis)
        frame = self.draw_probe_creation_overlay(frame)
        frame = self.draw_mask_creation_overlay(frame)
        if self.show_masks:
            frame = self.draw_mask_overlay(frame)
        if self.show_probes:
            frame = self.draw_probe_overlay(frame)
        if self.show_cursor:
            frame = self.draw_cursor_overlay(frame)
        if self.show_grid:
            frame = self.draw_grid_overlay(frame,
                    self.view_settings.grid_spacing)
        if self.show_center_cross:
            frame=self.draw_center_cross(frame)
        
        self.process_logging()
        return frame
    
    def create_display_frame(self, width=None, height=None):
        self.acquire()
        return self.create_display_frame_from_current(width, height)
    
    def set_view_center(self, x, y):
        self.view_settings.center_x = int(x)
        self.view_settings.center_y = int(y)
    
    def crop_zoom_frame(self, frame):
        zoom = self.view_settings.zoom
        h, w = frame.shape[:2]
        # Full image
        if zoom <= 1.0:
            self.viewport.x1 = 0
            self.viewport.y1 = 0
            self.viewport.x2 = w
            self.viewport.y2 = h
            self.viewport.zoom = 1.0
            return frame

        # Zoomed view
        crop_w = max(8, int(w / zoom))
        crop_h = max(8, int(h / zoom))

        cx = self.view_settings.center_x
        cy = self.view_settings.center_y

        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)

        x2 = x1 + crop_w
        y2 = y1 + crop_h

        if x2 > w:
            x2 = w
            x1 = max(0, w - crop_w)

        if y2 > h:
            y2 = h
            y1 = max(0, h - crop_h)

        # Store viewport
        self.viewport.x1 = x1
        self.viewport.y1 = y1
        self.viewport.x2 = x2
        self.viewport.y2 = y2
        self.viewport.zoom = zoom

        cropped = frame[y1:y2, x1:x2]
        return cropped
    
    def reset_view(self):
        self.view_settings.center_x = (self.THERMAL_W // 2)
        self.view_settings.center_y = (self.THERMAL_H // 2)
        self.set_zoom(1.0)
        
    def temperature_to_display(self, tx, ty, width, height):
        vp = self.viewport
        px = int((tx - vp.x1) * width / (vp.x2 - vp.x1))
        py = int((ty - vp.y1) * height / (vp.y2 - vp.y1))
        px = max(0,min(width - 0, px))
        py = max(0,min(height - 0, py))
        return px, py
    
    def display_to_temperature(self, px, py, width, height):
        vp = self.viewport
        tx = int(vp.x1 + px * (vp.x2 - vp.x1) / width)
        ty = int(vp.y1 + py * (vp.y2 - vp.y1) / height)
        tx = max(0, min(self.THERMAL_W - 0, tx))
        ty = max(0, min(self.THERMAL_H - 0, ty))
        return tx, ty
    
    #--------------------
    # Visualization
    #--------------------
    def draw_text(self, frame, text, position, settings:TempTextSettings):
        tpos=self.clamp_text_position(frame,position[0],position[1],text,settings)
        if settings.shadow:
            tpos_sh=(tpos[0]+2,tpos[1]+2)
            cv2.putText(
                frame,
                text,
                tpos_sh,
                cv2.FONT_HERSHEY_SIMPLEX,
                settings.font_scale,
                (0,0,0),
                settings.thickness
            )

        cv2.putText(
            frame,
            text,
            tpos,
            cv2.FONT_HERSHEY_SIMPLEX,
            settings.font_scale,
            settings.color,
            settings.thickness
        )
        return frame
    
    def set_text_size(self, scale):
        self.txt_sett_cursor.font_scale = scale
        self.txt_sett_hot.font_scale = scale
        self.txt_sett_cold.font_scale = scale
        self.txt_sett_probe.font_scale = scale

    def clamp_text_position(self, frame, x, y, text, settings:TempTextSettings):
        h, w = frame.shape[:2]
        (tw, th), baseline = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            settings.font_scale,
            settings.thickness)
        # Right edge
        if x + tw > w:
            x = w - tw - 2
        # Left edge
        if x < 0:
            x = 2
        # Top edge
        if y - th < 0:
            y = th + 2
        # Bottom edge
        if y > h:
            y = h - 2
        return x, y

    #--------------------
    # Live stream
    #--------------------
    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.view_settings.show_grid = self.show_grid
        self.set_zoom(self.view_settings.zoom)
    
    def toggle_hotspot(self):
        self.show_hotspot = not self.show_hotspot
        self.view_settings.show_hotspot = self.show_hotspot
        self.set_zoom(self.view_settings.zoom)

    def toggle_coldspot(self):
        self.show_coldspot = not self.show_coldspot
        self.view_settings.show_coldspot = self.show_coldspot
        self.set_zoom(self.view_settings.zoom)
    
    def toggle_cursor(self):
        self.show_cursor = not self.show_cursor
        self.view_settings.show_cursor = self.show_cursor
        self.set_zoom(self.view_settings.zoom)

    def toggle_masks(self):
        self.show_masks = not self.show_masks
        self.view_settings.show_masks = self.show_masks
        self.set_zoom(self.view_settings.zoom)

    def toggle_probes(self):
        self.show_probes = not self.show_probes
        self.view_settings.show_probes = self.show_probes
        self.set_zoom(self.view_settings.zoom)

    def toggle_center_cross(self):
        self.show_center_cross = not self.show_center_cross
        self.view_settings.show_center_cross = self.show_center_cross
        self.set_zoom(self.view_settings.zoom)
    
    def zoom_in(self):
        self.set_zoom(self.view_settings.zoom * 1.25)
    
    def zoom_out(self):
        self.set_zoom(self.view_settings.zoom / 1.25)

    def fit_view(self):
        self.reset_view()

    def live_stream(self):
        window_name = ("HIKMICRO Native")
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name,
            self.view_settings.display_width, 
            self.view_settings.display_height)

        cv2.setMouseCallback(window_name, self.mouse_callback)

        self.log("ESC=Exit ",
                 "g=Grid ",
                 "h=Hotspot ",
                 "c=Coldspot ",
                 "p=Probes ",
                 "u=Cursor ",
                 "m=Masks ",
                 "x=Center_Cross ",
                 "+=Zoom_In ",
                 "-=Zoom_Out ",
                 "#=Fit_All ",
                 "s=Snapshot",
                 "k=Save_Config",
                 "l=Load_Config")

        while True:
            frame = self.create_display_frame(
                self.view_settings.display_width,
                self.view_settings.display_height
            )

            cv2.imshow(window_name, frame)
            key = (cv2.waitKey(1) & 0xFF)
            if key == 27 or key == ord('q'):
                break

            elif key in (ord('k'), ord('K')):
                filename = self.get_timestamped_filename(
                    self.default_config)
                self.save_config(filename)

            elif key in (ord('l'), ord('L')):
                self.load_config(self.default_config)

            elif key in (ord('s'), ord('S')):
                filename = filename = self.get_timestamped_filename(
                    "native.png")
                cv2.imwrite(filename, frame)
                self.log(f"Saved {filename}")
            
            elif key in (ord('g'), ord('G')):
                self.toggle_grid()

            elif key in (ord('h'), ord('H')):
                self.toggle_hotspot()
            
            elif key in (ord('c'), ord('C')):
                self.toggle_coldspot()
            
            elif key in (ord('u'), ord('U')):
                self.toggle_cursor()
            
            elif key in (ord('m'), ord('M')):
                self.toggle_masks()

            elif key in (ord('p'), ord('P')):
                self.toggle_probes()

            elif key in (ord('x'), ord('X')):
                self.toggle_center_cross()    

            elif key == ord('+'):
                self.zoom_in()
                self.log("Zoom:", self.view_settings.zoom)

            elif key == ord('-'):
                self.zoom_out()
                self.log("Zoom:", self.view_settings.zoom)

            elif key == ord('#'):
                self.fit_view()
                
        cv2.destroyAllWindows()
    
    #--------------------
    # Calibration
    #--------------------
    def load_calibration_polynomial(self, filename):
        coeffs = np.load(filename)
        self.calibration.enabled = True
        self.calibration.calibration_type = "POLYNOMIAL"
        self.calibration.file_name = filename
        self.calibration.coeffs = coeffs
        self.state.calibration_changed = True
        self.emit_event(CameraEvent.CALIBRATION_CHANGED, self.calibration)
    
    def load_calibration_table(self, filename, delimiter=","):
        """csv table raw, Temp"""
        data = np.loadtxt(filename, delimiter, skiprows=1)
        self.calibration.enabled = True
        self.calibration.calibration_type = "TABLE"
        self.calibration.file_name = filename
        self.calibration.raw_values = data[:,0]
        self.calibration.temperature_values = data[:,1]
        self.state.calibration_changed = True
        self.emit_event(CameraEvent.CALIBRATION_CHANGED, self.calibration)
    
    def save_calibration(self, filename):
        if self.calibration.calibration_type == "POLYNOMIAL":
            np.save(filename, self.calibration.coeffs)
        elif self.calibration.calibration_type == "TABLE":   
            data = np.array(list(zip(self.calibration.raw_values, 
                self.calibration.temperature_values)))
            header = "Raw, Temp °C"  
            np.savetxt(filename,data,delimiter=",",header=header)
            
    def raw_to_celsius(self, raw_value):
        if not self.calibration.enabled:
            return float(raw_value)
        if self.calibration.calibration_type == "CALLBACK":
            if self.temperature_callback:
                return self.temperature_callback(
                            raw_value,
                            self.metadata_frame,
                            self
                        )

        if self.calibration.calibration_type == "POLYNOMIAL":
            return float(np.polyval(self.calibration.coeffs, raw_value))

        if self.calibration.calibration_type == "TABLE":
            return float(
                np.interp(raw_value, self.calibration.raw_values, 
                          self.calibration.temperature_values))
        return float(raw_value)
    
    def celsius_to_unit(self,value_degc,unit=None):
        if unit is None:
            unit = (self.calibration.display_unit)
        if unit in ["°F","F"]:
            return self.celsius_to_fahrenheit(value_degc)
        if unit == "K":
            return self.celsius_to_kelvin(value_degc)
        if unit in ["°C","C"]:
            return value_degc
        return None
    
    def celsius_to_fahrenheit(self,value):
        return value * 9.0 / 5.0 + 32.0

    def celsius_to_kelvin(self, value):
        return value + 273.15
    
    def raw_to_temperature(self, raw_value,unit=None):
        if not self.calibration.enabled:
            return float(raw_value)
        celsius = self.raw_to_celsius(raw_value)
        in_unit=self.celsius_to_unit(celsius,unit)
        return in_unit if in_unit is not None else raw_value
    
    def get_temperature_display_map(self):
        raw = self.get_analysis_temperature_map()
        if not self.calibration.enabled:
            return raw.astype(np.float32)
        vectorized = np.vectorize(self.raw_to_temperature)
        return vectorized(raw).astype(np.float32)
    
    def get_calibration_info(self):
        return {
            "enabled": self.calibration.enabled,
            "type": self.calibration.calibration_type,
            "unit": self.calibration.display_unit,
            "file": self.calibration.file_name,
            "coeff_count":
                len(self.calibration.coeffs)
                if self.calibration.coeffs is not None
                else 0,
            "table_points":
                len(self.calibration.raw_values)
                if self.calibration.raw_values
                is not None
                else 0
        }
    
    def get_settings_model(self):
        return {
            "view": self.view_settings,
            "calibration": self.calibration,
            "viewport": self.viewport
        }

    def format_temperature(self, value, settings: TempTextSettings):
        # Raw mode
        if settings.unit == "Raw":
            return f"{value:.{settings.decimals}f}"
        # Convert raw -> display temperature
        temp = self.raw_to_temperature(value,settings.unit)
        return f"{temp:.{settings.decimals}f}{settings.unit}"
    
    def set_temperature_callback(self, callback):
        self.temperature_callback = callback
        self.state.calibration_changed = True
        self.emit_event(CameraEvent.CALIBRATION_CHANGED, self.calibration)
    
    def set_view_settings(self,view_setting:ViewSettings):
        self.view_settings=view_setting
        
    #--------------------
    # Scale bar
    #--------------------
    def create_scale_bar(self, width=96, height=768, vertical=True, tick_count=5):
        # Use calibrated values when available
        if self.calibration.enabled:
            temp_map = self.get_temperature_display_map()
        else:
            temp_map = self.get_temperature_map()

        tmin = float(np.min(temp_map))
        tmax = float(np.max(temp_map))

        settings = self.txt_sett_scale

        if vertical:
            color_width = 24
            gradient = np.linspace(255, 0, height, dtype=np.uint8).reshape(height, 1)
            gradient = np.repeat(gradient, color_width, axis=1)
            colored = cv2.applyColorMap(gradient, self.view_settings.colormap)
            # Leave room for text
            bar = np.zeros((height, width, 3), dtype=np.uint8)
            bar[:, :color_width] = colored

            for i in range(tick_count):
                y = int(i * (height - 1) / (tick_count - 1))
                value = (tmax - (tmax - tmin) * i / (tick_count - 1))
                text = self.format_temperature(value, settings)
                self.draw_text( bar, text,(color_width + 6, y + 5), settings)
            return bar

        # Horizontal
        color_height = 24
        gradient = np.linspace(0,255,width,dtype=np.uint8).reshape(1, width)
        gradient = np.repeat(gradient, color_height,axis=0)
        colored = cv2.applyColorMap(gradient,self.view_settings.colormap)
        bar = np.zeros((height, width, 3), dtype=np.uint8)

        bar[:color_height, :] = colored

        for i in range(tick_count):
            x = int(i * (width - 1) / (tick_count - 1))
            value = (tmin + (tmax - tmin) * i / (tick_count - 1))
            text = self.format_temperature(value, settings)
            self.draw_text(bar, text, (x, color_height + 18), settings)

        return bar
    
    def get_scale_range(self):
        if self.calibration.enabled:
            temp_map = self.get_temperature_display_map()
        else:
            temp_map = self.get_temperature_map()
        return (float(np.min(temp_map)), float(np.max(temp_map)))
    
    #--------------------
    # Rulers
    #--------------------
    
    def create_pixel_ruler_vertical(self, display_height, width=50, spacing=16):
        vp = self.viewport
        ruler = np.zeros((display_height, width, 3),
                        dtype=np.uint8)
        x = width - 8
        cv2.line(
            ruler,
            (x, 0),
            (x, display_height),
            (255,255,255),
            1
        )
        start = (vp.y1 // spacing) * spacing
        for image_y in range(start, vp.y2 + spacing, spacing):
            screen_y = int(
                (image_y - vp.y1)
                * display_height
                / (vp.y2 - vp.y1)
            )
            major = ((image_y // spacing) % 2) == 0
            tick_w = 12 if major else 6
            cv2.line(
                ruler,
                (x, screen_y),
                (x - tick_w, screen_y),
                (255,255,255),
                1
            )
            if major:
                self.draw_text(
                    ruler,
                    str(image_y),
                    (2, screen_y + 5),
                    self.txt_sett_ruler
                )
        return ruler
    
    def create_pixel_ruler_horizontal(self, display_width, height=50, spacing=16):
        vp = self.viewport
        ruler = np.zeros((height, display_width, 3),
                        dtype=np.uint8)
        y = height - 8
        cv2.line(
            ruler,
            (0, y),
            (display_width, y),
            (255,255,255),
            1
        )

        start = (vp.x1 // spacing) * spacing

        for image_x in range(start, vp.x2 + spacing, spacing):

            screen_x = int(
                (image_x - vp.x1)
                * display_width
                / (vp.x2 - vp.x1)
            )
            major = ((image_x // spacing) % 2) == 0
            tick = 12 if major else 6
            cv2.line(
                ruler,
                (screen_x, y),
                (screen_x, y - tick),
                (255,255,255),
                1
            )
            if major:
                self.draw_text(
                    ruler,
                    str(image_x),
                    (screen_x + 2, 12),
                    self.txt_sett_ruler
                )
        return ruler

    #--------------------
    # Event handling
    #--------------------
    def set_event_callback(self, callback):
        self.event_callback = callback
    
    def emit_event(self, event_type, data=None):
        event = EngineEvent(
            event_type=event_type, data=data, timestamp=time.time())
        self.event_history.append(event)

        if len(self.event_history) > 1000:
            self.event_history.pop(0)

        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception as ex:
                self.log(f"Event callback error: {ex}")
    
    def clear_state_flags(self):
        self.state.probes_changed = False
        self.state.calibration_changed = False
        self.state.settings_changed = False
        self.state.view_changed = False
        self.state.frame_ready = False
        self.state.error_changed = False
    
    def get_engine_info(self):
        return {
            "probe_count": len(self.probes),
            "mask_count": len(self.masks),
            "zoom": self.view_settings.zoom,
            "calibration_enabled": self.calibration.enabled,
            "calibration_type": self.calibration.calibration_type
        }
    
    #--------------------
    # Data Logging
    #--------------------
    def process_logging(self):
        ls = self.logging_settings
        if not ls.enabled:
            return
        now = time.time()
        if (now - self.last_log_time < ls.interval_s):
            return

        self.last_log_time = now
        self.log_sample()
    
    def build_log_row(self):
        globalinfo=self._get_global_dict()
        for probe in self.probes.values():
            if not isinstance(probe,ProbeArea):
                continue
            if not probe.log_enabled:
                continue
            p_dict = self._get_probe_dict(probe)
            for key,value in p_dict.items():
                if key != "probe": #if key is not "probe":
                    globalinfo.update({f"{probe.name}_{key}":value})
        for mask in self.masks.values():
            if not isinstance(mask,MaskArea):
                continue
            if not mask.log_enabled:
                continue
            m_dict = self._get_mask_dict(mask)
            for key,value in m_dict.items():
                if key != "mask": #if key is not "mask":
                    globalinfo.update({f"{mask.name}_{key}":value})

        return [globalinfo]
    
    def _get_mask_dict(self,mask:MaskArea):
        return {
                "mask"     : mask.name,
                "mode"   : mask.mode,
                "value"   : mask.raw_value,
                "normalize_max"   : mask.normalize_max,
                "normalize_min"   : mask.normalize_min,
            }
    
    def _get_probe_dict(self,probe:ProbeArea):
        return {
                "probe"     : probe.name,
                "average": probe.average_temp,
                "minimum": probe.minimum_temp,
                "maximum": probe.maximum_temp,

                "hotspot": probe.hotspot_temp,
                "hotspot_x": probe.hotspot_x,
                "hotspot_y": probe.hotspot_y,

                "coldspot": probe.coldspot_temp,
                "coldspot_x": probe.coldspot_x,
                "coldspot_y": probe.coldspot_y,

                "low_alarm_enabled":probe.low_alarm.enabled,
                "low_alarm_active"  : probe.low_alarm.active, 
                "high_alarm_enabled":probe.high_alarm.enabled,
                "high_alarm_active": probe.high_alarm.active,
            }
    
    def _get_global_dict(self):
        anal=self.analysis
        return {
            "timestamp" : self.last_log_time,
            "global_hotspot_temp": anal.hotspot_value,
            "global_hotspot_x": anal.hotspot_x,
            "global_hotspot_y": anal.hotspot_y,

            "global_coldspot_temp": anal.coldspot_value,
            "global_coldspot_x": anal.coldspot_x,
            "global_coldspot_y": anal.coldspot_y,

            "frame_average": anal.average_value,
            "frame_minimum": anal.minimum_value,
            "frame_maximum": anal.maximum_value,
        }
    
    def start_logging(self):
        if self.is_logging:
            return
        self.logging_settings.enabled = True
        self.log_start_time = time.time()
        self.last_log_time = 0
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log_file = (Path(self.logging_settings.output_path) /f"log_{timestamp}.csv")
        self.log(f"Logging started: {self.log_file}")
        self.is_logging = True
        self.state.is_logging = self.is_logging
        self.emit_event(CameraEvent.LOGGING_STARTED, self.logging_settings)
    
    def stop_logging(self):
        self.logging_settings.enabled = False
        self.log(f"Logging {self.log_file} stopped")
        self.is_logging = False
        self.state.is_logging = self.is_logging
        self.emit_event(CameraEvent.LOGGING_STOPPED, self.logging_settings)
    
    def start_video_recording(self):
        if self.is_video_recording:
            return
        self.video_settings.enabled = True
        self.video_recorder.start()
        self.is_video_recording = True
        
    
    def stop_video_recording(self):
        self.video_recorder.stop()
        self.video_settings.enabled = False
        self.is_video_recording = False
        
    
    def log_sample(self):
        rows = self.build_log_row()
        if not rows:
            return

        file_exists = (
            self.log_file.exists()
            if isinstance(self.log_file, Path)
            else Path(self.log_file).exists())
        if not file_exists and self.logging_settings.add_header:
            self.write_log_header()

        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=rows[0].keys())

            if not file_exists:
                writer.writeheader()

            for row in rows:
                writer.writerow(row)
    
    def write_log_header(self):

        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("#========================================\n")
            f.write("# HIKMICRO Native Log Session\n")
            f.write("#========================================\n")

            f.write(
                f"# Session Start: {datetime.now()}\n")
            f.write(
                f"# Camera Index: {self.camera_index}\n")

            f.write("\n")
            f.write("# Logging\n")
            for key, value in self.logging_settings.__dict__.items():
                f.write(f"#   {key}: {value}\n")
            f.write("\n")
            
            engine = self.get_engine_info()
            f.write("# Engine\n")
            for key, value in engine.items():
                f.write(
                    f"#   {key}: {value}\n"
                )
            f.write("\n")

            cal = self.get_calibration_info()
            f.write("# Calibration\n")
            for key, value in cal.items():
                f.write(
                    f"#   {key}: {value}\n"
                )

            f.write("\n")
            probes = self.get_probes_infos()
            skip = {
                "history",
                "timestamp",
                "average_temp",
                "minimum_temp",
                "maximum_temp",
                "hotspot_temp",
                "coldspot_temp"
            }
            f.write("# Probes\n")
            for name, probe in probes.items():
                f.write(f"#   {name}\n")
                for key, value in probe.items():
                    if key in skip:
                        continue
                    f.write(f"#      {key}: {value}\n")

            f.write("\n")
            masks = self.get_masks_infos()
            f.write("# Masks\n")
            for name, mask in masks.items():
                f.write(f"#   {name}\n")
                for key, value in mask.items():
                    f.write(f"#      {key}: {value}\n")
            f.write("\n")
            f.write("#========================================\n")
            f.write("# DATA STARTS BELOW\n")
    
    #--------------------
    # Update from setttings 
    #--------------------
    def apply_view_settings(self):
        self.show_grid = self.view_settings.show_grid
        self.show_hotspot = self.view_settings.show_hotspot
        self.show_coldspot = self.view_settings.show_coldspot 
        self.show_cursor = self.view_settings.show_cursor
        self.show_masks = self.view_settings.show_masks 
        self.show_probes = self.view_settings.show_probes 
        self.show_center_cross = self.view_settings.show_center_cross 
        self.set_zoom(self.view_settings.zoom)
    


###############################################################################
# MAIN
###############################################################################
   
if __name__ == "__main__":
    try:
        cam = HIKMICRO_NATIVE()
        # TEST CALIBRATION
        cam.calibration.enabled = True
        cam.calibration.calibration_type = "POLYNOMIAL"
        # T = 0.5 * raw - 20
        cam.calibration.coeffs = np.array([0.5,-20.0])
        # Display temperatures in °C
        cam.txt_sett_hot.unit = "°C"
        cam.txt_sett_cold.unit = "°C"
        cam.txt_sett_cursor.unit = "°C"
        # cam.save_native_debug()
        cam.acquire()
        analysis = cam.analyze_frame()
        print()
        print("HOT RAW:", analysis.hotspot_value)
        print("HOT °C:", 
              cam.raw_to_temperature(analysis.hotspot_value))
        print()
        print("COLD RAW:",analysis.coldspot_value)
        print("COLD °C:",
            cam.raw_to_temperature(analysis.coldspot_value))

        stats = cam.measure_area(
            analysis.hotspot_x, analysis.hotspot_y,radius=2)
        print()
        print("AREA AROUND HOTSPOT")
        print("MIN:",cam.raw_to_temperature(stats.minimum))
        print("MAX:",cam.raw_to_temperature(stats.maximum))
        print("AVG:",cam.raw_to_temperature(stats.average))
        print("STD:", stats.stddev)
        frame = cam.create_colormapped_frame(colormap=cam.view_settings.colormap,
                                              use_clahe=cam.view_settings.use_clahe)
        cv2.imwrite("colormapped.png", frame)

        cam.add_probe("TEST",50,50,120,120)
        # Make probe display
        cam.probes["TEST"].text_settings.unit = "°F"
        frame = cam.create_display_frame(1024,768)
        cv2.imwrite("display_test.png",frame)
        cam.live_stream()

    except Exception as ex:
        print(ex)