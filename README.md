# GazePoint Capture Plugin

A plugin for [**Multimodal Observer**](https://github.com/MultimodalObserver-2/mo) that records eye-tracking data from a Gazepoint GP3 device over a TCP connection and saves timestamped gaze samples to a text file.

## Features

- Records fixation, left/right, and best POG (Point of Gaze) coordinates
- Records pupil center coordinates and pupil diameter for both eyes
- Configurable device port
- Periodic autosave to prevent data loss
- Saves raw data in `.raw` format and a formatted output in `.txt`

## Configuration Options

| Property | Description | Default |
| -------- | ----------- | ------- |
| `config_name` | Configuration profile name | `Gazepoint_Config_1` |
| `device_port` | TCP port of the Gazepoint Control API | `4242` |
| `time_autosave` | Autosave interval in seconds (`5`, `10`, `15`, `20`) | `10` |

These can be set in the plugin configuration interface of Multimodal Observer.

## Output Format

The plugin outputs one line per sample in the following format:

```
t:{timestamp} st:7 fx:{fixated} sm:{x};{y} rw:{x};{y} lsm:{x};{y} lrw:{x};{y} lpc:{x};{y} lps:{diameter} rsm:{x};{y} rrw:{x};{y} rpc:{x};{y} rps:{diameter}
```

- `t`: Timestamp in milliseconds.
- `fx`: Whether a fixation was detected (`true` / `false`).
- `sm` / `rw`: Screen coordinates of the fixation and best POG (in pixels).
- `lsm`, `rsm`: Left and right eye POG coordinates.
- `lpc`, `rpc`: Left and right pupil center coordinates.
- `lps`, `rps`: Left and right pupil diameter.

## Installation

### 1. Build the plugin

```
build-mop -r requirements.txt
```

This generates the distributable `.zip` file inside the `dist/` folder.

### 2. Register the plugin

Open Multimodal Observer, go to the plugin interface, and register the `.zip` file located in the `dist/` folder.

## How It Works

- Connects to the Gazepoint Control API running on localhost via TCP.
- Sends configuration commands to enable all POG and pupil data streams.
- Reads XML-formatted data frames from the socket and parses gaze and pupil values.
- Coordinates are stored as normalized values (0–1) in the raw file and converted to screen pixels in the final output.
- Pause and resume are handled by blocking the read loop using a threading event.
