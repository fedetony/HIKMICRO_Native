import cv2
import numpy as np
import time
from pathlib import Path
from dataclasses import dataclass
from class_device_driver_finder import *

@dataclass
class TemperaturePoint:
    x: int
    y: int
    value: float


@dataclass
class ROIStats:
    minimum: float
    maximum: float
    average: float
    stddev: float

@dataclass
class ThermalFrameAnalysis:

    timestamp: float

    hotspot_x: int
    hotspot_y: int
    hotspot_value: float

    coldspot_x: int
    coldspot_y: int
    coldspot_value: float

    average_value: float
    minimum_value: float
    maximum_value: float

    frame_width: int
    frame_height: int

@dataclass
class ProbeArea:

    name: str

    x1: int
    y1: int

    x2: int
    y2: int

    hotspot_x: int = 0
    hotspot_y: int = 0
    hotspot_temp: float = 0

    coldspot_x: int = 0
    coldspot_y: int = 0
    coldspot_temp: float = 0

    average_temp: float = 0
    minimum_temp: float = 0
    maximum_temp: float = 0

    timestamp: float = 0

    history: list = None


class HIKMICRO:

    DISPLAY_W = 800
    DISPLAY_H = 600
    THERMAL_X1 = 150
    THERMAL_X2 = 312
    THERMAL_X3 = 231 # (312-150)/2+150

    THERMAL_Y1 = 0   # Start
    THERMAL_Y2 = 122 # Thermal image end/ info beguin
    THERMAL_Y3 = 127 # info end / thumbs begin
    THERMAL_Y4 = 185 # thumbs end / gary begin
    THERMAL_Y5 = 215 # gray end , footer begin
    THERMAL_Y6 = 220 # End

    def __init__(self, camera_index=None, log_callback=None):

        self.log = log_callback if log_callback else print
        self.width = 0
        self.height = 0
        self.mouse_x = 0
        self.mouse_y = 0
        #container for probes
        self.probes = {}

        if camera_index is None:
            camera_index = self.find_correct_camera()

        if camera_index is None:
            raise RuntimeError("No camera found")

        self.camera_index = camera_index

        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera {self.camera_index}"
            )

        self.log(
            f"Using thermal camera index {self.camera_index}"
        )

    ###########################################################################
    # Camera Management
    ###########################################################################

    def find_correct_camera(self):
        candidates = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if not cap.isOpened():
                continue
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                self.log(f"Camera {i}: {w}x{h}")
                candidates.append((i, w, h))

            cap.release()
        if not candidates:
            return None
        # prefer non-standard resolutions

        for i, w, h in candidates:
            if (w, h) != (640, 480):
                return i
        return candidates[0][0]

    def release(self):
        if self.cap is not None:
            self.cap.release()

    def __del__(self):
        try:
            self.release()
        except:
            pass
    
    def build_display_frame(self):
        #
        # Thermal colors
        #
        thermal = self.get_thumb1_roi()
        thermal = cv2.resize(
            thermal,
            (self.DISPLAY_W, self.DISPLAY_H),
            interpolation=cv2.INTER_NEAREST # Nearest is correct don't use linear or cubic
        )

        #
        # Edge image
        #
        edges = self.get_thermal_roi()
        edges = cv2.cvtColor(edges, cv2.COLOR_BGR2GRAY)
        edges = cv2.resize(
            edges,
            (self.DISPLAY_W, self.DISPLAY_H),
            interpolation=cv2.INTER_CUBIC)

        #
        # normalize edge visibility
        #
        edges = cv2.normalize(edges, None, 0, 255, cv2.NORM_MINMAX)

        edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        #
        # combine
        #
        overlay = cv2.addWeighted(thermal, 0.7, edges, 0.3, 0)
        return overlay
    ###########################################################################
    # Frame Capture
    ###########################################################################

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Cannot read frame")
        return frame

    def save_jpeg(self, filename=None):
        frame = self.get_frame()
        if filename is None:
            filename = (f"thermal_{int(time.time())}.jpg")
        cv2.imwrite(filename, frame)
        self.log(f"Saved {filename}")
        return filename
    
    def save_thermal_jpeg(self):
        roi = self.get_thermal_roi()
        filename = f"thermal_roi_{int(time.time())}.jpg"
        cv2.imwrite(filename, roi)
        self.log(f"Saved {filename}")
        return filename
    
    def save_sections(self):
        frame = self.get_frame()

        sections = {
            "thermal": frame[self.THERMAL_Y1:self.THERMAL_Y2, self.THERMAL_X1:self.THERMAL_X2],
            "info":    frame[(self.THERMAL_Y2+1):self.THERMAL_Y3, self.THERMAL_X1:self.THERMAL_X2],
            "thumbs":  frame[(self.THERMAL_Y3+1):self.THERMAL_Y4, self.THERMAL_X1:self.THERMAL_X2],
            "footer":  frame[(self.THERMAL_Y4+1):self.THERMAL_Y5, self.THERMAL_X1:self.THERMAL_X2],
            "tail":    frame[(self.THERMAL_Y5+1):self.THERMAL_Y6, self.THERMAL_X1:self.THERMAL_X2],
        }

        for name, img in sections.items():
            cv2.imwrite(f"debug_thermal_{name}.png", img)

    ###########################################################################
    # Temperature Map
    ###########################################################################
    
    def get_thermal_roi(self):
        frame = self.get_frame()

        return frame[
            self.THERMAL_Y1:self.THERMAL_Y2,
            self.THERMAL_X1:self.THERMAL_X2
        ]
    
    def get_thumb1_roi(self):
        frame = self.get_frame()

        return frame[
            (self.THERMAL_Y3+1):self.THERMAL_Y4,
            self.THERMAL_X1:self.THERMAL_X3
        ]
    
    def get_thumb2_roi(self):
        frame = self.get_frame()

        return frame[
            (self.THERMAL_Y3+1):self.THERMAL_Y4,
            self.THERMAL_X3:self.THERMAL_X2
        ]
    
    def get_temperature_map(self):
        frame = self.get_thumb1_roi()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return gray.astype(np.float32)
    
    def debug_snapshot(self):
        frame = self.get_frame()
        cv2.line(
            frame,
            (0, self.THERMAL_Y2),
            (frame.shape[1], self.THERMAL_Y2),
            (0, 0, 255),
            2
        )
        cv2.imwrite("debug_crop.jpg", frame)

    ###########################################################################
    # Hot/Cold Analysis
    ###########################################################################
    def overlay_thumb1_colormap(self):
        main = self.get_thermal_roi()
        thumb = self.get_thumb1_roi()

        gray = cv2.cvtColor(
            thumb,
            cv2.COLOR_BGR2GRAY
        )

        thermal = cv2.applyColorMap(
            gray,
            cv2.COLORMAP_INFERNO
        )

        thermal_big = cv2.resize(
            thermal,
            (main.shape[1], main.shape[0]),
            interpolation=cv2.INTER_CUBIC
        )

        overlay = cv2.addWeighted(
            main,
            0.4,
            thermal_big,
            0.6,
            0
        )
        return overlay
    
    def compare_views(self):

        main = self.get_thermal_roi()

        thumb1 = cv2.resize(
            self.get_thumb1_roi(),
            (main.shape[1], main.shape[0]),
            interpolation=cv2.INTER_NEAREST
        )

        thumb2 = cv2.resize(
            self.get_thumb2_roi(),
            (main.shape[1], main.shape[0]),
            interpolation=cv2.INTER_NEAREST
        )

        combined = np.hstack([
            main,
            thumb1,
            thumb2
        ])

        cv2.imshow(
            "Main | Thumb1 | Thumb2",
            combined
        )

        cv2.waitKey(0)
    
    def compare_thumbs(self):
        
        thumb1 = cv2.cvtColor(
            self.get_thumb1_roi(), cv2.COLOR_BGR2GRAY)

        thumb2 = cv2.cvtColor(
            self.get_thumb2_roi(), cv2.COLOR_BGR2GRAY)
        
        print("thumb1 shape:", thumb1.shape)
        print("thumb2 shape:", thumb2.shape)

        diff = cv2.absdiff(thumb1, thumb2)

        print("max diff :", diff.max())
        print("mean diff:", diff.mean())

        cv2.imwrite("thumb_diff.png",diff)

        print("Correlation: ",
            np.corrcoef(
                thumb1.flatten(),
                thumb2.flatten()
            )[0,1]
        )

        thumb1 = self.get_thumb1_roi()

        big = cv2.resize(
            thumb1,
            (800, 600),
            interpolation=cv2.INTER_NEAREST
        )

        cv2.imwrite(
            "thumb1_pixels.png",
            big
        )


    def hotspot(self, temp_map):
        blur = cv2.GaussianBlur(temp_map, (5,5), 0)
        y, x = np.unravel_index(np.argmax(blur), blur.shape)
        return TemperaturePoint(int(x),int(y), float(blur[y,x]))

    def coldspot(self,temp_map):
        blur = cv2.GaussianBlur(temp_map, (5,5), 0)
        y, x = np.unravel_index(np.argmin(blur), blur.shape)
        return TemperaturePoint(int(x),int(y), float(blur[y,x]))
    
    def mouse_callback(self, event, x, y, flags, param):
        self.mouse_x = x
        self.mouse_y = y
    


    ###########################################################################
    # Point Measurement
    ###########################################################################

    def measure_point(self, x, y):
        temp_map = self.get_temperature_map()
        return float(temp_map[y, x])

    ###########################################################################
    # ROI Statistics
    ###########################################################################

    def measure_rectangle(self, x, y, width, height):
        temp_map = self.get_temperature_map()
        roi = temp_map[y:y + height, x:x + width]
        return ROIStats(
            minimum=float(np.min(roi)),
            maximum=float(np.max(roi)),
            average=float(np.mean(roi)),
            stddev=float(np.std(roi))
        )

    ###########################################################################
    # Threshold Detection
    ###########################################################################

    def detect_hot_objects(self, threshold=200):
        temp_map = self.get_temperature_map()
        mask = (temp_map > threshold).astype(np.uint8)
        count, labels = cv2.connectedComponents(mask)
        results = []

        for idx in range(1, count):
            ys, xs = np.where(labels == idx)
            if len(xs) == 0:
                continue
            results.append(
                {
                    "pixels": len(xs),
                    "max": float(temp_map[ys, xs].max()),
                    "avg": float(temp_map[ys, xs].mean()),
                    "center": (int(xs.mean()), int(ys.mean()))
                }
            )
        return results

    ###########################################################################
    # Mouse ROI Selection
    ###########################################################################

    def select_roi(self):
        frame = self.get_thermal_roi() #self.get_frame()
        x, y, w, h = cv2.selectROI("Select ROI", frame, showCrosshair=True)
        cv2.destroyWindow("Select ROI")

        if w == 0 or h == 0:
            return None

        stats = self.measure_rectangle(
            int(x), int(y), int(w), int(h))

        return (int(x), int(y), int(w), int(h), stats)

    ###########################################################################
    # Visualization
    ###########################################################################

    def draw_analysis_overlay(self, frame):

        temp_map = self.get_temperature_map()

        hot = self.hotspot(temp_map)
        cold = self.coldspot(temp_map)

        sx = frame.shape[1] / temp_map.shape[1]
        sy = frame.shape[0] / temp_map.shape[0]

        hx = int(hot.x * sx)
        hy = int(hot.y * sy)

        cx = int(cold.x * sx)
        cy = int(cold.y * sy)

        tx = int(self.mouse_x / sx) # cursor 
        ty = int(self.mouse_y / sy)

        tx = max(0, min(tx, temp_map.shape[1]-1))
        ty = max(0, min(ty, temp_map.shape[0]-1))

        cursor_temp = temp_map[ty, tx]

        cv2.drawMarker(frame, (hx, hy),
            (0, 0, 255), cv2.MARKER_CROSS, 30, 2)

        cv2.drawMarker(frame, (cx, cy),
            (255, 0, 0), cv2.MARKER_CROSS, 30, 2)

        cv2.putText(frame, f"HOT:{hot.value:.0f}", (hx + 10, hy - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.putText(frame, f"COLD:{cold.value:.0f}", (cx + 10, cy - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # cursor
        cv2.putText(frame, 
            f"T:{cursor_temp:.1f}", (self.mouse_x + 10, self.mouse_y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)
        
        return frame


    ###########################################################################
    # Live View
    ###########################################################################

    def live_stream(self):

        self.log("ESC=Exit | S=Save | R=ROI")
        is_registered = False
        while True:
            frame = self.build_display_frame()
            frame = self.draw_analysis_overlay(frame)
            cv2.imshow("HIKMICRO Thermal", frame)
            if not is_registered:
                cv2.namedWindow("HIKMICRO Thermal")
                cv2.setMouseCallback("HIKMICRO Thermal", self.mouse_callback)
                is_registered = True
            key = cv2.waitKey(1) & 0xFF

            if key == 27: # ESC
                break

            elif key == ord('s'):
                filename = (f"snapshot_{int(time.time())}.jpg")
                cv2.imwrite(filename, frame)
                self.log(f"Saved {filename}")

        cv2.destroyAllWindows()

    ###########################################################################
    # Reporting
    ###########################################################################

    def report(self,temp_map):
        hot = self.hotspot(temp_map)
        cold = self.coldspot(temp_map)
        return {
            "hotspot": hot,
            "coldspot": cold
        }
    
    ###########################################################################
    # New additional functions
    ###########################################################################

    def measure_area(
            self,
            center_x,
            center_y,
            radius=0):

        temp_map = self.get_temperature_map()

        x1 = max(0, center_x - radius)
        y1 = max(0, center_y - radius)

        x2 = min(
            temp_map.shape[1],
            center_x + radius + 1
        )

        y2 = min(
            temp_map.shape[0],
            center_y + radius + 1
        )

        roi = temp_map[
            y1:y2,
            x1:x2
        ]

        return ROIStats(
            minimum=float(np.min(roi)),
            maximum=float(np.max(roi)),
            average=float(np.mean(roi)),
            stddev=float(np.std(roi))
        )

    def analyze_probe(self, probe:ProbeArea):

        temp_map = self.get_temperature_map()

        roi = temp_map[
            probe.y1:probe.y2,
            probe.x1:probe.x2
        ]

        min_val = np.min(roi)
        max_val = np.max(roi)

        avg_val = np.mean(roi)

        hot_y, hot_x = np.unravel_index(
            np.argmax(roi),
            roi.shape
        )

        cold_y, cold_x = np.unravel_index(
            np.argmin(roi),
            roi.shape
        )

        probe.timestamp = time.time()

        probe.minimum_temp = float(min_val)
        probe.maximum_temp = float(max_val)
        probe.average_temp = float(avg_val)

        probe.hotspot_x = probe.x1 + int(hot_x)
        probe.hotspot_y = probe.y1 + int(hot_y)

        probe.coldspot_x = probe.x1 + int(cold_x)
        probe.coldspot_y = probe.y1 + int(cold_y)

        probe.hotspot_temp = float(max_val)
        probe.coldspot_temp = float(min_val)

        return probe
    
    def get_frame_info(self):
        return {
            "frame": self.build_display_frame(),
           # "analysis": self.analyze_frame(),
            "probes": self.probes
        }
    
    def try_native_capture(self):

        frame = self.get_native_frame()
        print("Shape:", frame.shape)
        print("Dtype:", frame.dtype)

        #
        # Thermal image
        #
        thermal = frame[:192, :, 0]

        print(
            "Thermal:",
            thermal.shape,
            thermal.dtype,
            thermal.min(),
            thermal.max()
        )
        cv2.imwrite("native_capture.png", thermal)

        #
        # Metadata rows
        #
        metadata = frame[192:196, :, 0]

        metadata_big = cv2.resize(
            metadata, (1024, 200), interpolation=cv2.INTER_NEAREST)

        cv2.imwrite("metadata_rows.png", metadata_big)

        #
        # Inferno preview
        #
        preview = cv2.applyColorMap(thermal, cv2.COLORMAP_INFERNO)

        cv2.imwrite("native_capture_inferno.png", preview)

        print("Saved:")
        print("  native_capture.png")
        print("  native_capture_inferno.png")
        print("  metadata_rows.png")
    
    def get_native_temperature_map(self):
        raw = self.get_native_frame()
        return raw[:,:,0].astype(np.float32)
    
    def get_native_frame(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUY2"))
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 256)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 196)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise RuntimeError("Cannot read native frame")

        if frame.shape == (1, 100352):
            frame = frame.reshape(196, 256, 2)
        return frame
    
    def try_other_configs(self):
        for backend in (
            cv2.CAP_ANY,
            cv2.CAP_DSHOW,
            cv2.CAP_MSMF,
            cv2.CAP_V4L2,
        ):

            cap = cv2.VideoCapture(
                self.camera_index,
                backend
            )

            ret, frame = cap.read()

            if ret:
                print(
                    backend,
                    frame.shape,
                    frame.dtype
                )

            cap.release()

    def try_windows_pipeline(self):
        print("\n=== WINDOWS PIPELINE TEST ===\n")

        backends = [
            ("ANY",   cv2.CAP_ANY),
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF",  cv2.CAP_MSMF),
        ]

        resolutions = [
            (256, 192),
            (256, 196),
            (320, 240),
            (463, 220),
            (640, 480),
        ]

        fourccs = [
            "YUY2",
            "MJPG",
            "RGB3",
        ]

        test_id = 0

        for backend_name, backend in backends:

            print(f"\n{'=' * 60}")
            print(f"BACKEND : {backend_name}")
            print(f"{'=' * 60}")

            for fourcc_name in fourccs:
                for width, height in resolutions:
                    try:
                        cap = cv2.VideoCapture(self.camera_index, backend)
                        if not cap.isOpened():
                            continue

                        cap.set(
                            cv2.CAP_PROP_FOURCC,
                            cv2.VideoWriter_fourcc(*fourcc_name)
                        )
                        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                        time.sleep(0.2)
                        ret, frame = cap.read()
                        if not ret:
                            cap.release()
                            continue

                        print(
                            f"\n[{test_id}] "
                            f"{backend_name} "
                            f"{fourcc_name} "
                            f"{width}x{height}"
                        )
                        print("    shape:", frame.shape)
                        print("    dtype:", frame.dtype)
                        print("    min/max:", frame.min(), frame.max())
                        if frame.shape == (1, 100352):
                            raw = frame.reshape(196, 256, 2)
                            y = raw[:,:,0]
                            cv2.imwrite(f"decoded_{test_id}.png", y)
                            print("Decoded as:", raw.shape)
                            print(frame.shape)
                            print(frame[0,0:20])

                        if frame.shape == (1, 73728):
                            print("Interesting packed format")
                        # #
                        # # Save frame
                        # #
                        # filename = (
                        #     f"pipeline_"
                        #     f"{test_id:03d}_"
                        #     f"{backend_name}_"
                        #     f"{fourcc_name}.png"
                        # )
                        # try:
                        #     if len(frame.shape) == 3:
                        #         #
                        #         # save first channel
                        #         #
                        #         cv2.imwrite(filename, frame[:, :, 0])
                        #     else:
                        #         cv2.imwrite(filename, frame)
                        # except Exception:
                        #     pass
                        test_id += 1
                        cap.release()

                    except Exception as e:
                        print("    ERROR:", e)
    
    def decode_yuyv_buffer(self,frame):
        raw = frame.reshape(196, 256, 2)
        return raw[:,:,0]

###############################################################################
# MAIN
###############################################################################

if __name__ == "__main__":
    try:
        cam = HIKMICRO()    
        frame = cam.get_frame()
        print("Shape:", frame.shape)
        print("Dtype:", frame.dtype)
        print("Min:", frame.min())
        print("Max:", frame.max())
        # cam.debug_snapshot()
        # cam.save_thermal_jpeg()
        # cam.save_sections()
        
        cmd=""
        while cmd not in ("exit","q","quit"):
            cmd=input("Type any 'sn' to Enter Snapshot\n"
                      "Type any 'st' to Enter Stream\n"
                      "Type any 'd' to Enter Debug\n"
                      )
            while cmd.lower() == 'sn':
                if in_val not in ("","sn"):
                    break
                print("\n--- Snapshot ---")
                cam.save_jpeg()
                in_val=input("Type any letter to quit, Press Enter for new Snapshot")
                
            # print("\n--- Analysis ---")
            # print("Hotspot:", cam.hotspot())
            # print("Coldspot:", cam.coldspot())
            if 'st' == cmd.lower():
                print("\nStarting live view...\n")
                cam.live_stream()
            if 'd' == cmd.lower():
                print("\nStarting debug function...\n")
                # cam.compare_views()
                cam.compare_thumbs()
            if cmd.lower() == "n":
                cam.try_native_capture()
            if cmd.lower() == "o":
                print("\nTesting other configurations...\n")
                cam.try_other_configs()
            if cmd.lower() == "p":
                print("\nTesting Windows pipelines...\n")
                cam.try_windows_pipeline()



        cam.release()
    except Exception as eee:
        print(f"General Error: {eee}")
