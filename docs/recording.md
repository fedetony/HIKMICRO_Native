## Video Recording

### Raw Thermal Recording

HIKMICRO Native records raw thermal information instead of simply recording rendered thermal images.

Recordings are stored in NPZ format and contain the original thermal measurement data produced by the camera. This preserves the underlying thermal information and allows recordings to be reprocessed later using different visualization, calibration and analysis settings.

Unlike conventional screen recording, recordings are not tied to the display settings that were active during acquisition. The NPZ recording architecture is intended to provide a reusable source for both video generation and subsequent measurement logging.

Stored information may include:

- Raw thermal measurements.
- Thermal frame timestamps.
- Probe and mask information.
- Camera metadata when available.
- Additional processing information required for post-processing.

This makes a recording reusable for future analysis and video generation.

### Memory Efficient Recording

Thermal recordings are stored using a batched recording architecture.

Captured frames are periodically written into NPZ batches and merged into the final recording structure. This avoids storing the complete recording in RAM.

Benefits:

- Lower memory consumption.
- Long-duration recordings.
- Improved stability.
- Reduced risk of exhausting available memory.

Recordings can therefore be performed for long periods without requiring the complete thermal history to remain resident in memory.

### Logging and Recording are Independent

Temperature logging and thermal recording are separate features.

Logging records measurement information such as:

- Temperatures.
- Probe statistics.
- Timestamps.
- Measurement positions.

Recording stores raw thermal frame data.

Either system can be enabled independently.

Examples:

| Logging | Recording | Purpose |
|----------|----------|----------|
| Enabled | Disabled | Long-term temperature monitoring |
| Disabled | Enabled | Thermal recording for later analysis |
| Enabled | Enabled | Full acquisition and analysis history |

This allows storage requirements to be adjusted for the application.

### Post-Processing

Because recordings store raw thermal measurements rather than rendered video frames, recordings can be processed multiple times using different settings.
Hence, recorded thermal data can be used to generate new exports.

Because the raw thermal information is preserved, users can change visualization settings after recording. The same recording can be processed multiple times with different presentation settings.

For example:

- Select a different colormap.
- Change image visualization parameters.
- Apply different display settings.
- Different overlays.
- Probe visibility changes.
- Mask visibility changes.
- Generate a new MP4 video.
- Generate new measurement logs from the recorded information.

This means the final video does not have to be determined entirely by the settings used during acquisition.

#### Video export configuration

The export configuration includes:

- Video format.
- Frame rate.
- Report generation.
- Report title and subtitle.
- Company information.
- Timestamp visibility.
- Application version visibility.
- Measurement statistics.

The current export format is MP4.

### Export Reports

The MP4 video export system uses the same report configuration as screenshot reports.

Report settings are configured under:
```json
{
    "video": {
        "video_export": {
            "report": {
                ...
            }
        }
    }
}
```

The report configuration controls:

- Report title.
- Report subtitle.
- Company information.
- Timestamp visibility.
- Application version visibility.
- Measurement statistics.

Because screenshot reports and video reports share the same configuration structure, report appearance remains consistent across exported screenshots and generated videos.

Changes to the report configuration automatically affect both export mechanisms.

