## Alarm System

Each probe supports independent high-temperature and low-temperature alarms.

Supported alarm features:

- Enable/disable.
- Threshold configuration.
- Above-threshold alarms.
- Below-threshold alarms.
- Custom alarm messages.
- Alarm colors.
- Visual alarm indication.
- External trigger execution.

Example:
```json
{
    "high_alarm": {
        "enabled": true,
        "threshold": 120,
        "alarm_type": "ABOVE",
        "message": "OVER TEMP"
    }
}
```

## External Alarm Triggers

Alarm actions can launch external applications whenever an alarm becomes active.

Supported targets include:

- Python scripts (.py)
- Windows batch files (.bat, .cmd)
- Linux shell scripts (.sh)
- Native executables (.exe)
- Any executable program supported by the operating system

External triggers are executed by the thermal engine itself and therefore work in:

- PyQt GUI mode.
- OpenCV interface mode.
- Virtual Camera mode.
- Automated workflows.

### Trigger Configuration Example
```json
{
    "trigger_settings": {
        "enabled": true,
        "trigger_once": true,
        "executable": "scripts/high_temperature_alarm.py"
    }
}
```

### Trigger Execution

Triggers are executed when an alarm transitions from:

Alarm OFF
    ->
Alarm ON

The trigger is not continuously executed while the alarm remains active.

When trigger_once is enabled, the trigger is executed only once for the activation event.

This prevents accidental repeated execution during continuous alarm conditions.

## Python Trigger Example

import sys

print("Alarm Triggered")

for index, value in enumerate(sys.argv):
    print(index, value)

Example output:

Probe1
HIGH
145.0

## Windows Batch Trigger Example

@echo off

echo Alarm Triggered
echo Probe: %1
echo Alarm Type: %2
echo Value: %3

pause

## Linux Shell Trigger Example

#!/bin/bash

echo "Alarm Triggered"
echo "Probe: $1"
echo "Alarm Type: $2"
echo "Value: $3"


