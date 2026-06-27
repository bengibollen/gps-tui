# Adafruit Ultimate GPS GNSS Management Notes

This document collects notes for managing the Adafruit Ultimate GPS GNSS with
USB, product ID 4279, from `gps-tui`.

The dashboard should continue to use `gpsd` for live position/satellite data.
Module management is a separate feature track because it sends control commands
to the GPS module and may change device state.

## Hardware Summary

The Adafruit USB board presents the GPS module as USB serial. Adafruit lists the
current product as:

- GPS + GLONASS support
- 99 search channels
- 1 to 10 Hz update rate
- NMEA 0183 output at 9600 baud by default
- built-in datalogging
- USB serial converter onboard

Adafruit's current product page says the board is built around an MTK3333 GNSS
chipset. The broader Adafruit Ultimate GPS guide and older downloadable command
documents are written around MTK3339/PA6-series modules. Adafruit says the
post-2021 PA1616D module has equivalent functionality, but this means `gps-tui`
should identify the device and verify command responses before assuming every
old MTK3339/LOCUS detail applies.

Sources:

- Adafruit product page: https://www.adafruit.com/product/4279
- Adafruit Ultimate GPS guide: https://learn.adafruit.com/adafruit-ultimate-gps
- Adafruit downloads page: https://learn.adafruit.com/adafruit-ultimate-gps/downloads

## gpsd vs Direct Serial

Use gpsd for:

- live position data
- satellite data
- fix quality
- normal dashboard panels

Use PMTK/module management for:

- querying firmware/version
- changing output sentence selection
- changing update rate
- changing baud rate
- LOCUS logger status/start/stop/dump/erase

There are two ways to send PMTK commands:

1. Through gpsd `?DEVICE` hex writes, while gpsd owns the device.
2. By opening `/dev/ttyUSB0` directly, with gpsd stopped or not using the port.

`gps-tui-device` uses the gpsd path by default. It opens a raw watch, sends PMTK
commands through `?DEVICE={"path":...,"hexdata":...}`, and captures `PMTKLOG` or
`PMTKLOX` from the raw stream. This follows the same basic path as `gpsctl -x`
without shelling out. Direct serial remains a fallback, but the app must avoid
fighting gpsd for the same serial device when using that mode.

Sources:

- gpsctl manual: https://gpsd.gitlab.io/gpsd/gpsctl.html
- gpsd manual: https://gpsd.gitlab.io/gpsd/gpsd.html

## PMTK Command Format

PMTK commands are NMEA-style text packets:

```text
$PMTK<type>[,<args>]*<checksum>\r\n
```

The checksum is XOR of all bytes between `$` and `*`, rendered as two uppercase
hex digits.

Example packets from the vendor docs:

```text
$PMTK000*32
$PMTK220,1000*1F
$PMTK251,38400*27
```

The module answers PMTK commands with `PMTK001` acknowledgements:

```text
$PMTK001,<command>,<flag>*<checksum>
```

Ack flags:

- `0`: invalid command or packet
- `1`: unsupported command
- `2`: valid command, action failed
- `3`: valid command, action succeeded

Source:

- PMTK command packet A11 PDF: https://cdn-shop.adafruit.com/datasheets/PMTK_A11.pdf

## Useful PMTK Commands

These are candidates for a future read-only/config screen.

### Query Firmware

```text
PMTK605
```

Expected response:

```text
PMTK705,...
```

Purpose:

- identify firmware/release string
- useful before enabling chipset-specific features

### Set Update Rate

```text
PMTK220,<milliseconds>
```

Examples:

```text
PMTK220,1000   # 1 Hz
PMTK220,200    # 5 Hz
PMTK220,100    # 10 Hz
```

Notes:

- The product supports 1 to 10 Hz.
- Higher update rates may require a higher baud rate if many NMEA sentences are
  enabled.
- This should be a confirmed write operation in the UI.

### Set Baud Rate

```text
PMTK251,<baud>
```

Supported values in the PMTK docs include:

```text
4800, 9600, 14400, 19200, 38400, 57600, 115200
```

Notes:

- Treat this as risky. A bad baud change can make the device appear silent until
  software reconnects at the new rate or the module resets.
- gpsctl explicitly warns that speed changes can fail or hang some USB/Bluetooth
  GPS setups.
- Do not make this a casual dashboard control.

### Configure NMEA Sentence Output

```text
PMTK314,...
```

Purpose:

- enable/disable NMEA sentence types such as GGA, GSA, GSV, RMC, VTG, etc.

Notes:

- Useful if we want fewer serial bytes at high update rates.
- For live dashboard use through gpsd, changing sentence output can affect what
  gpsd sees. Add this only after testing against the real module.

## LOCUS Built-In Logger

The built-in logger is called LOCUS.

Adafruit's guide says the logger stores date, time, latitude, longitude, and
altitude in onboard flash. The guide describes the logger as low-resolution:
logging happens only when there is a fix, and their guide says every 15 seconds
for the tested configuration. The current product page also lists built-in
datalogging.

The GlobalTop LOCUS manual describes a more general LOCUS system with modes and
content bitmaps, but also notes that some configuration is set by GlobalTop.
On the tested Adafruit MTK3333/PA1616D module, the logging type appears to be
firmware-fixed to FullStop. `PMTK_LOCUS_CONFIG`/`PMTK187` only gives us a
practical way to adjust the interval. Do not plan on switching this module to
cyclic/overwrite logging from `gps-tui`.

Sources:

- Built-in logging guide: https://learn.adafruit.com/adafruit-ultimate-gps/built-in-logging
- LOCUS manual PDF: https://cdn-shop.adafruit.com/datasheets/GTop%20LOCUS%20Library%20User%20Manual-v13.pdf

## LOCUS Commands

### Query Logger Status

```text
PMTK183
```

Expected response:

```text
PMTKLOG,<serial>,<type>,<mode>,<content>,<interval>,<distance>,<speed>,<status>,<number>,<percent>
```

Fields to display:

- log serial number
- logging type: overlap or full-and-stop
- mode flags
- content bitmap
- interval/distance/speed settings
- status: logging or stopped
- record count
- flash used percentage

This is the safest first LOCUS feature to implement.

Observed on the Adafruit module:

```text
type 1 = FullStop / stop when full
```

The type appears to be firmware-fixed. Treat it as status, not as a configurable
setting.

### Start or Stop Logger

```text
PMTK185,0   # start
PMTK185,1   # stop
```

Expected response:

```text
PMTK001,185,3
```

This should require confirmation because it changes module state.

Implemented as:

```sh
gps-tui-device locus-start --device /dev/ttyUSB0
gps-tui-device locus-stop --device /dev/ttyUSB0
```

Observed on the Adafruit MTK3333/PA1616D module:

```text
PMTKLOG status 0 = logging
PMTKLOG status 1 = stopped
```

### Erase Logger Flash

```text
PMTK184,1
```

Expected response:

```text
PMTK001,184,3
```

This must require explicit confirmation. Prefer a typed confirmation such as
`ERASE`.

### Dump Logger Data

```text
PMTK622,0   # dump full flash
PMTK622,1   # dump used flash
```

Expected flow:

```text
PMTKLOX,0,n
PMTKLOX,1,0,<hex chunks...>
PMTKLOX,1,1,<hex chunks...>
...
PMTKLOX,1,n-1,<hex chunks...>
PMTKLOX,2
PMTK001,622,3
```

Implementation notes:

- Use gpsd raw watch plus `?DEVICE` by default. This has been tested for LOCUS
  status and is the current default transport in `gps-tui-device`.
- Keep direct serial as a fallback only.
- Save the raw `PMTKLOX` dump first before trying to parse it.
- Parse/export can come after raw download works.
- The LOCUS manual recommends 115200 baud for reliable dumping, but changing
  baud has its own risks. Test at the module's current baud first.
- Because this module is FullStop, the archive workflow should dump, verify,
  optionally convert, then erase and restart logging. Otherwise the logger will
  eventually fill and stop.

### Temporary LOCUS Interval Config

```text
PMTK187,1,<seconds>
```

The LOCUS manual describes this as a temporary interval change. The field
description says `PMTK187,mode,setting`, but the printed example includes an
extra comma: `$PMTK,187,1,5*38`. The checksum in that example matches
`PMTK187,1,5`, so this looks like a typo in the rendered command text.

On the tested Adafruit module this should be treated as the only practical
LOCUS configuration knob. It can change the logging interval, but not the
firmware-fixed FullStop/overwrite type.

## Proposed gps-tui Feature Plan

### Phase 1: Read-Only Device Inspection

Implemented as a management/debug command outside the main TUI:

```sh
gps-tui-device locus-status --device /dev/ttyUSB0
```

- Query firmware with `PMTK605`.
- Query LOCUS status with `PMTK183`.
- Print raw responses and parsed fields.
- PMTK is sent through gpsd by default.

### Phase 2: LOCUS Raw Dump

Implemented as:

```sh
gps-tui-device locus-dump --device /dev/ttyUSB0 --output locus.pmtklox
```

If `--output` is omitted, the command writes a compact timestamped filename:

```text
yyyymmddhhmmss.pmtklox
```

For now this is based on dump time unless a recognizable textual timestamp is
present in the captured data. Once the LOCUS record format is decoded, the
filename should use the first logged track point timestamp.

- Store raw `PMTKLOX` lines.
- Include metadata from `PMTK183`.
- Add timeout/progress handling.
- Use gpsd raw watch plus `?DEVICE` by default.
- Keep direct serial available as a fallback with `--transport serial`.

`dump-locus` is also available as an alias, but `locus-dump` is the preferred
name for consistency with `locus-status`.

GPX conversion is not enabled yet. LOCUS dumps arrive as `PMTKLOX` hex chunks,
and the first implementation should preserve those raw chunks exactly. Once we
have a sample from the actual Adafruit module, a parser can convert the logged
position records to GPX while optionally keeping module-specific metadata in the
raw `.pmtklox` file.

The Adafruit guide describes LOCUS as storing date, time, latitude, longitude,
and altitude. It does not describe separate start/stop event records. Treat
start/stop as logger state changes rather than track events unless a real dump
from this module proves otherwise.

### Phase 3: Safe Writes

Add only after read-only and dump paths are reliable:

- start logger
- stop logger
- erase logger flash with explicit confirmation
- temporary LOCUS interval setting

Do not add a logging type switch unless a specific tested command exists for
this exact module/firmware. Current evidence says the type is fixed to FullStop.

Recommended FullStop archive flow:

```text
1. query status
2. stop logger, optional but safest for a stable snapshot
3. dump used flash to raw .pmtklox
4. verify PMTKLOX completion and PMTK001 ack
5. parse/convert when parser exists
6. erase only after explicit confirmation
7. start logger again
```

This can create a small logging gap while stopped. Avoiding the gap means
dumping while logging, but for FullStop mode we still need a later erase to
prevent the logger from filling permanently.

### Phase 4: TUI Management Screen

Once the command layer is reliable, add a TUI screen:

- logger status
- storage usage
- record count
- start/stop buttons/keys
- dump progress
- erase with typed confirmation
- archive flow for FullStop mode: dump, verify, erase, restart
- raw command/result log

## Open Questions for the Pi

Run these on the Pi and save the output:

```sh
lsusb
gpsctl /dev/ttyUSB0
gpsmon /dev/ttyUSB0
stty -F /dev/ttyUSB0
```

If gpsd owns the device, also check:

```sh
gpspipe -w -n 10
```

These outputs will tell us:

- exact USB serial bridge
- how gpsd identifies the receiver
- current baud/settings
- whether PMTK responses are visible through gpsd
- whether direct serial access is clean while gpsd is running

## Safety Rules for Implementation

- Default management operations to read-only.
- Do not change baud rate from the TUI in the first implementation.
- Do not erase LOCUS data without typed confirmation.
- Save raw dumps before parsing.
- Treat missing/failed PMTK acknowledgements as failure.
- Keep module management separate from the live dashboard loop.
- Prefer explicit user action over background configuration changes.
