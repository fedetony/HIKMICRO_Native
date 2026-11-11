## Video Export Workflow

Video export is designed to work with both live and offline thermal data.

### Live Camera Recording

When a camera is connected:

1. The active thermal configuration is used.
2. Thermal frames are recorded into an NPZ recording.
3. Recording continues until stopped by the user.

### Offline Video Rendering

When no camera is connected and the user starts a video export:

1. A settings JSON file is requested.
2. An NPZ recording is selected.
3. An output MP4 filename is selected.
4. The recording is replayed using Virtual Camera mode.
5. Frames are processed using the selected settings.
6. An MP4 video is generated.

The camera is locked during the export process to prevent conflicts between acquisition and rendering operations.

### Why Raw Thermal Recording?

Recording raw thermal measurements makes it possible to re-render videos later using different display settings.

Examples:

- Change from Inferno to Jet colormap.
- Enable or disable overlays.
- Change calibration coefficients.
- Modify probe visibility.
- Update report information.
- Regenerate output videos.

The final appearance of the exported video does not need to be decided at acquisition time.

## Virtual Camera Mode

Virtual Camera mode allows NPZ recordings to be replayed as if a real thermal camera were connected.

The thermal engine receives data from the recording instead of a physical camera.

Virtual Camera mode is useful for:

- Development.
- Debugging.
- Calibration testing.
- Video rendering.
- Training.
- Automated processing.
- Reproducible testing.

The same thermal processing pipeline is used for:

- Live cameras.
- Virtual cameras.

This ensures that thermal analysis, alarms, probes, masks and trackers behave consistently in both modes.

Virtual Camera mode can also be used when generating MP4 videos from existing recordings.

