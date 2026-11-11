## Measurement regions: Probes and Masks

The application supports two independent types of measurement regions: probes and masks.

Although both use rectangular regions, they have different purposes.

### 7.1 Probes

Probes are measurement regions used to monitor temperatures within selected areas of the thermal image.

Each probe can have its own:

- Name.
- Position and dimensions.
- Measurement mode.
- Temperature unit.
- Decimal precision.
- Display color.
- Hotspot and coldspot detection.
- Logging configuration.
- High-temperature alarm.
- Low-temperature alarm.

Multiple probes can be created and monitored independently.

Probe names can be configured directly in the JSON configuration. A graphical renaming function is planned but is not yet implemented.

#### Probe interaction

**OpenCV interface and Qt interface:**

- Ctrl + Left-click and drag: Create a probe.
- Ctrl + Right-click: Delete the nearest probe to the clicked position.

The Ctrl modifier is intentional: it prevents accidental probe creation when clicking the interface to change focus or interact with other controls.

### 7.2 Masks

Masks are regions used to control how areas of the thermal image are considered during analysis and visualization.

They are particularly useful when certain objects or areas should be excluded, normalized or treated differently.

For example, a hot object can remain visible in the thermal image without constantly becoming the global hotspot or triggering temperature alarms.

Masks can also cover areas that should not be displayed or inspected.

#### Mask interaction

**OpenCV interface and Qt interface:**

- Shift + Left-click and drag: Create a mask.
- Shift + Right-click: Delete the nearest mask to the clicked position.

Mask interaction is handled separately from probe interaction and uses the corresponding mask controls.

#### Mask operating modes

Masks support different processing modes:

**1. Fixed raw value**

The mask uses a configured raw sensor value.

This allows a region to be represented using a fixed value rather than its original thermal measurements.

**2. Maximum value**

The region uses its maximum raw measurement value.

**3. Minimum value**

The region uses its minimum raw measurement value.

**4. Normalized**

Normalization scales the raw values within a configurable minimum and maximum range.

For example:
```json
    {
        "mode": "NORMALIZED",
        "normalize_min": 10,
        "normalize_max": 128
    }
```
This is particularly useful when dealing with hot objects or regions that would otherwise dominate the thermal image.

Normalization preserves the visual context of the thermal scene while preventing normalized values from being treated as actual temperature measurements for hotspot detection and alarm evaluation.

The original thermal measurements remain important and should not be confused with normalized visualization values.

#### Practical examples

Masks can be used to:

- Prevent a permanently hot object from dominating hotspot detection.
- Exclude irrelevant areas from thermal inspection.
- Normalize selected regions to improve image visualization.
- Cover areas that should not participate in inspection.
- Control how specific regions contribute to thermal analysis.

Probes and masks can coexist in the same thermal image.

## 8. Alarms

Probes support independent high-temperature and low-temperature alarms.

Each alarm can configure:

- Activation state.
- Threshold.
- Comparison type.
- Blink behavior.
- Display color.
- Alarm message.

Example:
```json
    {
        "high_alarm": {
            "enabled": true,
            "threshold": 120,
            "alarm_type": "ABOVE",
            "blink": true,
            "color": [0, 0, 255],
            "message": "OVER TEMP"
        }
    }
```
Supported comparison types include:

- ABOVE
- BELOW

Alarms are functional, although some implementation details and integration work remain in development.

## 9. Logging and recording

Logging and thermal recording are independent operations.

The application distinguishes between measurement logging and raw thermal data acquisition.

### 9.1 Temperature logging

Temperature logging is implemented and tested.

The logger records thermal measurement information over time, including:

- Temperature measurements.
- Measurement positions.
- Timestamps.

Logging can be configured globally and for individual measurement regions where supported.

The logging configuration controls:

- Logging interval.
- Duration.
- Maximum file size.
- Output format.
- Destination directory.
- Timestamped filenames.
- CSV headers.

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

A duration of 0.0 indicates no configured time limit.

