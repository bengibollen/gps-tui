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

There are two likely ways to send PMTK commands:

1. Through `gpsctl -x`, while gpsd owns the device.
2. By opening `/dev/ttyUSB0` directly, with gpsd stopped or not using the port.

`gpsctl` can send control strings through gpsd with `-x`, but it expects a
complete NMEA command including `$`, checksum, and line ending for text packets.
Direct serial access gives more control for reading long LOCUS dumps, but the
app must avoid fighting gpsd for the same serial device.

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
That means our first implementation should query status and dump data before
assuming the interval/content can be changed safely on this Adafruit module.

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

- Use direct serial for this unless `gpsctl -x` plus gpsd gives reliable access
  to the complete multi-line dump.
- Save the raw `PMTKLOX` dump first before trying to parse it.
- Parse/export can come after raw download works.
- The LOCUS manual recommends 115200 baud for reliable dumping, but changing
  baud has its own risks. Test at the module's current baud first.

### Temporary LOCUS Interval Config

```text
PMTK187,1,<seconds>
```

The LOCUS manual describes this as a temporary interval change. The field
description says `PMTK187,mode,setting`, but the printed example includes an
extra comma: `$PMTK,187,1,5*38`. The checksum in that example matches
`PMTK187,1,5`, so this looks like a typo in the rendered command text.

Treat this as experimental until tested on the actual Adafruit USB module. It
also belongs behind an explicit confirmation because it changes logger behavior.

## Proposed gps-tui Feature Plan

### Phase 1: Read-Only Device Inspection

- Add a management/debug command outside the main TUI first, for example:

```sh
python3 -m gps_tui.device --device /dev/ttyUSB0 status
```

- Query firmware with `PMTK605`.
- Query LOCUS status with `PMTK183`.
- Print raw responses and parsed fields.
- No writes.

### Phase 2: LOCUS Raw Dump

- Add:

```sh
python3 -m gps_tui.device --device /dev/ttyUSB0 dump-locus --output locus.txt
```

- Store raw `PMTKLOX` lines.
- Include metadata from `PMTK183`.
- Add timeout/progress handling.
- Keep gpsd interaction explicit:
  - either stop gpsd before direct serial access
  - or use a gpsd/gpsctl path if testing proves it captures full dumps

### Phase 3: Safe Writes

Add only after read-only and dump paths are reliable:

- start logger
- stop logger
- erase logger flash with explicit confirmation
- temporary LOCUS interval setting

### Phase 4: TUI Management Screen

Once the command layer is reliable, add a TUI screen:

- logger status
- storage usage
- record count
- start/stop buttons/keys
- dump progress
- erase with typed confirmation
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
