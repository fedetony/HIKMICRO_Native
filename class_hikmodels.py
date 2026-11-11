import cv2
import numpy as np
from enum import Enum
from dataclasses import dataclass, field, asdict
from collections import deque

class CameraEvent(Enum):
    PROBE_ADDED = "probe_added"
    PROBE_REMOVED = "probe_removed"
    PROBE_CHANGED = "probe_changed"
    MASK_ADDED = "mask_added"
    MASK_REMOVED = "mask_removed"
    MASK_CHANGED = "mask_changed"
    CALIBRATION_CHANGED = "calibration_changed"
    SETTINGS_CHANGED = "settings_changed"
    FRAME_READY = "frame_ready"
    VIEW_CHANGED = "view_changed"
    ACQUIRE_ERROR = "acquire_error"
    LOG_MESSAGE = "log_message"
    ALARM_TRIGGERED_H = "high_alarm_triggered"
    ALARM_TRIGGERED_L = "low_alarm_triggered"
    ALARM_CLEARED_H = "high_alarm_cleared"
    ALARM_CLEARED_L = "low_alarm_cleared"
    CONFIGURATION_LOADED = "configuration_loaded"
    LOGGING_STARTED = "logging_started"
    LOGGING_STOPPED = "logging_stopped"
    VIDEO_REC_STARTED = "video_started"
    VIDEO_REC_STOPPED = "video_stopped"

class MaskMode(Enum):
    EXCLUDE = "exclude"
    CONSTANT = "constant"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    NORMALIZED = "normalized"

class TempMode(Enum):
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    DEVIATION = "deviation"

class SnapshotType(Enum):
    CAM_RAW = "cam_raw"
    IMAGE_RAW = "image_raw"
    IMAGE_DISPLAY = "image_display"
    IMAGE_REPORT = "image_report"
    IMAGE_COMPLETE = "image_complete"

class ColorMap(Enum):
    AUTUMN = cv2.COLORMAP_AUTUMN
    BONE = cv2.COLORMAP_BONE
    JET = cv2.COLORMAP_JET
    WINTER = cv2.COLORMAP_WINTER
    RAINBOW = cv2.COLORMAP_RAINBOW
    OCEAN = cv2.COLORMAP_OCEAN
    SUMMER = cv2.COLORMAP_SUMMER
    SPRING = cv2.COLORMAP_SPRING
    COOL = cv2.COLORMAP_COOL
    HSV = cv2.COLORMAP_HSV
    PINK = cv2.COLORMAP_PINK
    HOT = cv2.COLORMAP_HOT
    PARULA = cv2.COLORMAP_PARULA
    MAGMA = cv2.COLORMAP_MAGMA
    INFERNO = cv2.COLORMAP_INFERNO
    PLASMA = cv2.COLORMAP_PLASMA
    VIRIDIS = cv2.COLORMAP_VIRIDIS
    CIVIDIS = cv2.COLORMAP_CIVIDIS
    TWILIGHT = cv2.COLORMAP_TWILIGHT
    TWILIGHT_SHIFTED = cv2.COLORMAP_TWILIGHT_SHIFTED
    TURBO = cv2.COLORMAP_TURBO
    DEEPGREEN = cv2.COLORMAP_DEEPGREEN

class OriginType(Enum):
    CAM = "cam"
    QT = "qt"
    NONE = None

class ConfigMixin:
    CONFIG_SKIP = set()
    
    def to_data_dict(self):
        keep = self.CONFIG_SKIP
        d = asdict(self)
        all_keys=list(d.keys())
        for key in all_keys:
            if key not in keep:
                d.pop(key, None)
        return d
    
    def todict(self):
        return asdict(self)
    
    def update_from_dict(self, config_dict: dict):
        current = asdict(self)
        if not isinstance(config_dict,dict):
            return self
        for key, value in config_dict.items():
            if key in self.CONFIG_SKIP:
                continue
            if key not in current:
                continue
            attr = getattr(self, key)
            if isinstance(attr, ConfigMixin) and isinstance(value, dict):
                attr.update_from_dict(value)
            else:
                setattr(self, key, value)
        return self
    
    def _serialize(self, value):
        if isinstance(value, Enum):
            return value.name
        if isinstance(value, dict):
            return {
                k: self._serialize(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [
                self._serialize(v)
                for v in value
            ]
        return value

    def to_config_dict(self):
        d = asdict(self)
        for key in self.CONFIG_SKIP:
            d.pop(key, None)
        return self._serialize(d)



@dataclass
class EngineState:
    probes_changed: bool = False
    masks_changed: bool = False
    calibration_changed: bool = False
    settings_changed: bool = False
    view_changed: bool = False
    frame_ready: bool = False
    error_changed: bool = False
    alarm_triggered_h: bool = False
    alarm_triggered_l: bool = False
    is_logging: bool = False
    is_video_recording: bool = False

@dataclass
class EngineEvent:
    event_type: CameraEvent
    data: object = None
    timestamp: float = 0

@dataclass
class EventHandler:
    event: EngineEvent = field(
            default_factory=EngineEvent
        )
    origin: str = None
    timestamp: float = 0
    ini_state: EngineState = field(
            default_factory=EngineState
        )
    end_state: EngineState = field(
            default_factory=EngineState
        )

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
class TempTextSettings(ConfigMixin):
    unit: str = "Raw"
    decimals: int = 1
    font_scale: float = 0.4
    thickness: int = 1
    color: tuple = (255,255,255)

    shadow: bool = True
    # show_raw: bool = False
    mode: TempMode = TempMode.AVERAGE

@dataclass
class TriggerSettings(ConfigMixin):
    enabled: bool = False
    executable: str = ""
    trigger_once: bool =True
    trigger_count: int = 0

    CONFIG_SKIP = {
        "trigger_count",
        }

@dataclass
class AlarmSettings(ConfigMixin):
    enabled: bool = True
    threshold: float = 120
    alarm_type: str = "ABOVE"
    blink: bool = True
    color: tuple = (0,0,255)
    message: str = "OVER TEMP"
    active: bool = False
    trigger_settings: TriggerSettings = field(
            default_factory=TriggerSettings
        )
    CONFIG_SKIP = {
        "active",
        }

@dataclass
class TrackerSettings(ConfigMixin):
    enabled: bool = False
    label: str = "Temperature"
    apply_calibration: bool = True
    color_avg: str = "#00ff00"
    color_min: str = "#0088ff"
    color_max: str = "#ff0000"
    line_width: int = 2
    line_style: str = "solid"

@dataclass
class ProbeArea(ConfigMixin):
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

    history: deque = field(
        default_factory=lambda: deque(maxlen=1000))
    log_enabled: bool = True

    # display
    color: tuple = (0,255,0)
    text_settings: TempTextSettings = field(
            default_factory=TempTextSettings
        )
    tracker_settings: TrackerSettings = field(
            default_factory=TrackerSettings
        )
    visible: bool = True
    show_hotspot: bool = True
    show_coldspot: bool = True
    line_thickness: int = 1

    #Alarms
    high_alarm: AlarmSettings = field(
        default_factory=lambda: 
        AlarmSettings(enabled=False,
                      alarm_type= "ABOVE",
                      message = "OVER TEMP"))
    low_alarm: AlarmSettings = field(
        default_factory=lambda: 
        AlarmSettings(enabled=False,
                      alarm_type= "BELOW",
                      message = "UNDER TEMP"))
    CONFIG_SKIP = {
            "history",
            "timestamp",

            "hotspot_x",
            "hotspot_y",
            "hotspot_temp",

            "coldspot_x",
            "coldspot_y",
            "coldspot_temp",

            "average_temp",
            "minimum_temp",
            "maximum_temp",
        }
        

@dataclass
class ViewSettings(ConfigMixin):
    display_width: int = 800
    display_height: int = 600
    zoom: float = 1.0

    center_x: int = 128
    center_y: int = 96

    show_hotspot: bool = True
    show_coldspot: bool = True

    show_grid: bool = False
    show_probes: bool = True
    show_masks:bool = True
    show_probe_labels: bool = True
    show_cursor: bool = True
    show_scale_bar_v: bool = True
    show_scale_bar_h: bool = False
    show_ruler_v: bool = False
    show_ruler_h: bool = False
    
    use_clahe: bool = True
    colormap: ColorMap = ColorMap.INFERNO 

    show_scale_bar: bool = True
    show_center_cross: bool = False
    show_metadata: bool = False

    grid_spacing: int = 16
    CONFIG_SKIP = {
        "display_width",
        "display_height"
    }

@dataclass
class LoggingSettings(ConfigMixin):
    enabled: bool = False
    interval_s: float = 1.0
    duration_s: float = 0.0
    max_file_size_mb: int = 100
    format: str = "csv" #"parquet"
    output_path: str = "."
    append_timestamp: bool = True
    add_header: bool = True

@dataclass
class ReportSettings(ConfigMixin):
    title: str = "Thermal Inspection"
    subtitle: str = ""
    company: str = "HIKMICRO"
    # footer_text: str = "with Coffee & Love"

    show_title: bool = True
    show_timestamp: bool = True
    show_version: bool = True
    show_statistics: bool = True

@dataclass
class VideoExportSettings(ConfigMixin):
    record_report: bool = True
    fps: float = 0.0
    vid_format: str = "mp4"
    report: ReportSettings = field(
        default_factory=ReportSettings
    )

@dataclass
class VideoSettings(ConfigMixin):
    enabled: bool = False
    filename_prefix: str = "video_"
    # record_display: bool = False
    # record_report: bool = True
    # record_raw: bool = True
    # vid_format: str = "mp4"
    raw_format: str = "npz"
    # fps: float = 2.0
    # sync_logger: bool = False
    # log_rate: int = 5
    append_timestamp: bool = True
    video_export:VideoExportSettings = field(
        default_factory=VideoExportSettings
    )

@dataclass
class Viewport(ConfigMixin):
    # Visible thermal area
    x1: int = 0
    y1: int = 0
    x2: int = 256
    y2: int = 192
    # Current zoom factor
    zoom: float = 1.0

    @property
    def width(self):
        return self.x2 - self.x1
    @property
    def height(self):
        return self.y2 - self.y1

@dataclass
class CalibrationSettings(ConfigMixin):
    enabled: bool = False
    calibration_type: str = "RAW" #RAW, POLYNOMIAL, TABLE
    file_name: str = ""
    coeffs: np.ndarray = None
    raw_values: np.ndarray = None
    temperature_values: np.ndarray = None
    display_unit: str = "°C"

    def to_config_dict(self):
        """Json->np.array exceptions"""
        d = super().to_config_dict()
        if d["coeffs"] is not None:
            d["coeffs"] = d["coeffs"].tolist()

        if d["raw_values"] is not None:
            d["raw_values"] = d["raw_values"].tolist()

        if d["temperature_values"] is not None:
            d["temperature_values"] = (
                d["temperature_values"].tolist()
            )
        return d
    
    def update_from_dict(self, config_dict):
        """Json->np.array exceptions"""
        super().update_from_dict(config_dict)
        if self.coeffs is not None:
            self.coeffs = np.array(self.coeffs)

        if self.raw_values is not None:
            self.raw_values = np.array(self.raw_values)

        if self.temperature_values is not None:
            self.temperature_values = np.array(
                self.temperature_values
            )

@dataclass
class MaskArea(ConfigMixin):
    name: str
    x1: int
    y1: int
    x2: int
    y2: int

    enabled: bool = True
    raw_value: int = 128
    mode: MaskMode = MaskMode.CONSTANT
    normalize_min: int = 100
    normalize_max: int = 150
    log_enabled: bool = False
    # Display
    visible: bool = True
    color: tuple = (255, 0, 255)
    
    line_thickness: int = 1
    text_settings: TempTextSettings = field(
        default_factory=TempTextSettings
    )

    CONFIG_SKIP = set()