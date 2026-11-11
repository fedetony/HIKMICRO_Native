# Configuration Reference

Related documentation:

- [Recording and Video Export](recording.md)
- [Virtual Camera Mode](virtual_camera.md)
- [Trackers](trackers.md)
- [Alarms and External Triggers](alarms.md)
- [Probes and Masks](probes_and_masks.md)

##  Configuration Reference

The entire application is designed around a JSON configuration file.

The default configuration file is:

    hik_default_config.json

The configuration controls visualization, measurements, calibration, logging, video recording, probes and masks.

This makes it possible to configure the application without modifying its Python source code.

The configuration can be loaded and saved through the application.

You can also modify the JSON file manually.

### Application

```json
    {
        "application": {
            "name": "HIKMICRO Native",
            "version": "1.0.0"
        }
    }
```
Contains application identification and version information.

### View configuration

Controls the thermal image visualization.

| Parameter | Description |
|---|---|
| zoom | Image zoom level |
| center_x | Horizontal image center |
| center_y | Vertical image center |
| show_hotspot | Display hotspot |
| show_coldspot | Display coldspot |
| show_grid | Display image grid |
| show_probes | Display measurement probes |
| show_masks | Display masks |
| show_probe_labels | Display probe labels |
| show_cursor | Display cursor information |
| show_scale_bar_v | Display vertical scale bar |
| show_scale_bar_h | Display horizontal scale bar |
| show_ruler_v | Display vertical ruler |
| show_ruler_h | Display horizontal ruler |
| use_clahe | Enable CLAHE image enhancement |
| colormap | OpenCV colormap identifier |
| show_scale_bar | Enable general scale bar |
| show_center_cross | Display center cross |
| show_metadata | Display metadata |
| grid_spacing | Grid spacing |

Boolean parameters control visibility and rendering options.

### Logging

Logging can be enabled independently of video recording.

Example:
```json
    {
        "logging": {
            "enabled": true,
            "interval_s": 1.0,
            "duration_s": 0.0,
            "max_file_size_mb": 100,
            "format": "csv",
            "output_path": ".",
            "append_timestamp": true,
            "add_header": true
        }
    }
```

| Parameter | Description |
|---|---|
| enabled | Enable or disable logging |
| interval_s | Logging interval in seconds |
| duration_s | Logging duration; 0 indicates no configured time limit |
| max_file_size_mb | Maximum log file size |
| format | Logging output format |
| output_path | Destination directory |
| append_timestamp | Append timestamp to filename |
| add_header | Include CSV header |

Logging is intended to capture thermal measurement information over time.

### Video Recording and Export

The video subsystem consists of two separate stages:

1. Raw thermal recording.
2. Video rendering and export.

Example:
```json
{
    "video": {
        "enabled": false,
        "filename_prefix": "video_",
        "raw_format": "npz",
        "append_timestamp": true,

        "video_export": {
            "record_report": true,
            "fps": 0.0,
            "vid_format": "mp4",

            "report": {
                "title": "Thermal Inspection",
                "subtitle": "",
                "company": "HIKMICRO",

                "show_title": true,
                "show_timestamp": true,
                "show_version": true,
                "show_statistics": true
            }
        }
    }
}
```

### Report Settings

The report configuration is shared between:

- Screenshot reports.
- MP4 video export reports.

This ensures a consistent presentation format across all generated output.

Example:

```json
{
    "report": {
        "title": "Thermal Inspection",
        "subtitle": "",
        "company": "HIKMICRO",
        "show_title": true,
        "show_timestamp": true,
        "show_version": true,
        "show_statistics": true
    }
}
```

### Recording Settings

| Parameter | Description |
|------------|------------|
| enabled | Enable raw thermal recording |
| filename_prefix | Recording filename prefix |
| raw_format | Raw recording format |
| append_timestamp | Append timestamp to generated filenames |

### Export Settings

| Parameter | Description |
|------------|------------|
| record_report | Include inspection report |
| fps | Video frame rate (0 = automatic/default) |
| vid_format | Output video format |
| title | Report title |
| subtitle | Report subtitle |
| company | Company name |
| show_title | Display title page |
| show_timestamp | Display timestamps |
| show_version | Display application version |
| show_statistics | Display thermal statistics |

### Recording Workflow

Raw thermal recording stores sensor measurements rather than rendered video frames.

Recordings are saved in NPZ format and can later be processed using different visualization settings.

This allows:

- Changing colormaps after acquisition.
- Applying different calibration settings.
- Modifying overlays and annotations.
- Generating multiple MP4 exports from a single recording.
- Rendering recordings without requiring a connected camera.

### Offline Rendering Workflow

When no camera is connected, video export operates using Virtual Camera mode.

The export workflow is:

1. Select a settings JSON file.
2. Select the NPZ recording.
3. Select the output MP4 file.
4. Load the recording through Virtual Camera mode.
5. Apply the selected visualization settings.
6. Render and export the MP4 video.

During rendering the camera is locked to prevent simultaneous acquisition and export operations.

### Memory Efficient Recording

Raw recordings are written using a batched architecture.

Frames are periodically stored and merged into the final recording structure instead of accumulating indefinitely in memory.

This reduces memory consumption and allows long-duration thermal recordings.

### Viewport

Controls the active image region.

```json
    {
        "viewport": {
            "x1": 0,
            "y1": 0,
            "x2": 256,
            "y2": 192,
            "zoom": 1.0
        }
    }
```

| Parameter | Description |
|---|---|
| x1, y1 | Top-left coordinates |
| x2, y2 | Bottom-right coordinates |
| zoom | Viewport zoom |

### Calibration

Controls conversion of raw thermal measurements into temperature values.

```json
    {
        "calibration": {
            "enabled": true,
            "calibration_type": "POLYNOMIAL",
            "file_name": "",
            "coeffs": [0.5, -20.0],
            "raw_values": null,
            "temperature_values": null,
            "display_unit": "°C"
        }
    }
```

| Parameter | Description |
|---|---|
| enabled | Enable calibration |
| calibration_type | Calibration method |
| file_name | External calibration file |
| coeffs | Polynomial coefficients |
| raw_values | Calibration reference raw values |
| temperature_values | Corresponding temperature values |
| display_unit | Temperature display unit |

The supplied example uses polynomial calibration.

The actual polynomial coefficient order and interpretation depend on the calibration implementation.

Available display units should be checked against the engine's supported unit conversions.

### Cursor

Controls cursor measurement and appearance.
```json
    {
        "cursor": {
            "unit": "Raw",
            "decimals": 1,
            "font_scale": 0.45,
            "thickness": 1,
            "color": [255, 255, 255],
            "shadow": true,
            "mode": "AVERAGE"
        }
    }
```

| Parameter | Description |
|---|---|
| unit | Measurement unit |
| decimals | Decimal precision |
| font_scale | Text size |
| thickness | Text thickness |
| color | Text color in BGR order |
| shadow | Enable text shadow |
| mode | Measurement mode |

### Hotspot

Controls maximum temperature detection.
```json
    {
        "hotspot": {
            "unit": "Raw",
            "decimals": 1,
            "font_scale": 0.55,
            "thickness": 1,
            "color": [255, 0, 255],
            "shadow": true,
            "mode": "AVERAGE"
        }
    }
```

The configuration controls the displayed measurement, precision and appearance.

### Coldspot

Controls minimum temperature detection.

Uses the same structure as the hotspot configuration.

```json
    {
        "coldspot": {
            "unit": "Raw",
            "decimals": 1,
            "font_scale": 0.55,
            "thickness": 1,
            "color": [255, 255, 0],
            "shadow": true,
            "mode": "AVERAGE"
        }
    }
```

### Probes

Probes define independent thermal measurement regions.

Each probe performs continuous measurements within its configured region and maintains a history of measured values over time.

Multiple probes can be configured simultaneously.

Example:
```json
{
    "probes": [
        {
            "name": "TEST",
            "x1": 50,
            "y1": 50,
            "x2": 120,
            "y2": 120,

            "log_enabled": false,

            "color": [0, 255, 0],
            "visible": true,
            "show_hotspot": true,
            "show_coldspot": true,
            "line_thickness": 1,

            "text_settings": {
                "unit": "°F",
                "decimals": 1,
                "font_scale": 0.4,
                "thickness": 1,
                "color": [255,255,255],
                "shadow": true,
                "mode": "AVERAGE"
            },

            "tracker_settings": {
                "enabled": false,
                "label": "Temperature",
                "apply_calibration": true,
                "color_avg": "#00ff00",
                "color_min": "#0088ff",
                "color_max": "#ff0000",
                "line_width": 2,
                "line_style": "solid"
            }
        }
    ]
}
```

Each probe contains its own measurement, visualization, tracking and alarm configuration.

#### Probe Text Settings

Text settings control how probe measurements are displayed.

Example:

```json
{
    "text_settings": {
        "unit": "°F",
        "decimals": 1,
        "font_scale": 0.4,
        "thickness": 1,
        "color": [255,255,255],
        "shadow": true,
        "mode": "AVERAGE"
    }
}
```

Available settings include:

- Display unit.
- Decimal precision.
- Text size.
- Text thickness.
- Text color.
- Shadow effects.
- Measurement mode.

#### Probe Tracker Settings

Each probe can maintain a historical measurement record.

Trackers visualize the stored probe history using interactive plots.

Example:
```json
{
    "tracker_settings": {
        "enabled": true,
        "label": "Temperature",
        "apply_calibration": true,

        "color_avg": "#00ff00",
        "color_min": "#0088ff",
        "color_max": "#ff0000",

        "line_width": 2,
        "line_style": "solid"
    }
}
```

Tracker settings control:

- Tracker visibility.
- Plot label.
- Calibration application.
- Average curve color.
- Minimum curve color.
- Maximum curve color.
- Line width.
- Line style.

Trackers can be used during live acquisition or when replaying NPZ recordings through Virtual Camera mode.

#### High Temperature Alarm

Example:
```json
{
    "high_alarm": {
        "enabled": false,
        "threshold": 120,
        "alarm_type": "ABOVE",
        "blink": true,
        "color": [0,0,255],
        "message": "OVER TEMP",

        "trigger_settings": {
            "enabled": false,
            "executable": "",
            "trigger_once": true
        }
    }
}
```

The high temperature alarm becomes active when the measured value exceeds the configured threshold.

#### Low Temperature Alarm

Example:
```json
{
    "low_alarm": {
        "enabled": false,
        "threshold": 120,
        "alarm_type": "BELOW",
        "blink": true,
        "color": [0,0,255],
        "message": "UNDER TEMP",

        "trigger_settings": {
            "enabled": false,
            "executable": "",
            "trigger_once": true
        }
    }
}
```

The low temperature alarm becomes active when the measured value falls below the configured threshold.

#### Alarm Trigger Settings

Alarm triggers allow external applications to be executed whenever an alarm transitions from inactive to active.

Example:
```json
{
    "trigger_settings": {
        "enabled": true,
        "executable": "scripts/high_temperature_alarm.py",
        "trigger_once": true
    }
}
```

Supported trigger targets include:

- Python scripts (.py)
- Windows batch files (.bat, .cmd)
- Linux shell scripts (.sh)
- Native executables (.exe)
- Other executable files supported by the operating system

Triggers are executed by the thermal engine itself and therefore work in:

- PyQt GUI mode.
- OpenCV native mode.
- Virtual Camera mode.
- Automated workflows.

When trigger_once is enabled, the trigger is executed only once for each alarm activation event.

Each probe can independently configure:

- Measurement region.
- Measurement units.
- Decimal precision.
- Visualization color.
- Visibility.
- Hotspot display.
- Coldspot display.
- Logging.
- Historical tracking.
- Calibration behaviour for trackers.
- High-temperature alarms.
- Low-temperature alarms.
- Alarm thresholds.
- Alarm messages.
- Alarm visualization.
- External trigger execution.

Alarm thresholds are interpreted according to the selected measurement units and calibration settings used by the thermal engine.

### Masks

Masks define independent measurement regions.

Example:
```json
    {
        "masks": [
            {
                "name": "MASK NORMALIZED",
                "x1": 169,
                "y1": 40,
                "x2": 202,
                "y2": 126,
                "enabled": true,
                "raw_value": 128,
                "mode": "NORMALIZED",
                "normalize_min": 10,
                "normalize_max": 128,
                "log_enabled": false,
                "visible": true,
                "color": [0, 255, 255],
                "line_thickness": 1
            }
        ]
    }
```

| Parameter | Description |
|---|---|
| name | Mask identifier |
| x1, y1, x2, y2 | Region coordinates |
| enabled | Enable mask processing |
| raw_value | Raw measurement value |
| mode | Mask processing mode |
| normalize_min | Normalization minimum |
| normalize_max | Normalization maximum |
| log_enabled | Enable mask logging |
| visible | Display mask |
| color | Mask color |
| line_thickness | Outline thickness |

#### Mask text settings

Masks can also contain independent text settings, including unit, decimal precision, font size, color, shadow and measurement mode.

## 12. Configuration examples

### Enable logging

Set:
```json
    "logging": {
        "enabled": true
    }
```

Other logging parameters can be adjusted independently.

### Enable video recording

Set:
```json
    "video": {
        "enabled": true
    }
```
Configure the filename prefix, raw recording format and export settings as required.

### Add a measurement probe

Add an object to the probes array with the desired coordinates and measurement settings.

### Add a measurement mask

Add an object to the masks array.

Multiple probes and masks can be defined in the configuration.

## Configuration persistence

The JSON file is the central configuration source.

The application supports loading and saving configurations.

A saved configuration contains the application settings, visualization parameters, calibration, probes, masks, logging and video configuration.

The dt_when field stores the configuration timestamp.

The application version and configuration version are also stored to help identify configuration revisions.

Always keep a backup before manually editing the configuration file.