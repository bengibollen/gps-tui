# gps-tui

A small Python TUI for viewing GPS fix and satellite data from `gpsd`, intended
for a Raspberry Pi 3B+ over SSH.

The first version uses only the Python standard library:

- `curses` for the terminal UI
- a TCP socket connection to `gpsd` on `localhost:2947`
- optional simulation mode for development without GPS hardware
- a simple TOML theme file

## Run

From the project root:

```sh
python3 -m gps_tui --simulate
```

Against gpsd:

```sh
python3 -m gps_tui
```

Or install the console entry point:

```sh
python3 -m pip install -e .
gps-tui
```

Device management commands:

```sh
gps-tui-device locus-status --device /dev/ttyUSB0
gps-tui-device locus-start --device /dev/ttyUSB0
gps-tui-device locus-stop --device /dev/ttyUSB0
gps-tui-device locus-dump --device /dev/ttyUSB0 --output locus.pmtklox
```

Without `--output`, `locus-dump` writes to a compact timestamped filename:

```text
yyyymmddhhmmss.pmtklox
```

## Options

```text
--host HOST           gpsd host, default localhost
--port PORT           gpsd port, default 2947
--simulate            use generated GPS data instead of gpsd
--theme PATH          theme TOML file, default themes/btop-ish.toml
--refresh SECONDS     screen refresh interval, default 0.5
--geonames-dir PATH   GeoNames data directory, default data/geonames
```

## Keys

```text
q        quit
p        pause/resume updates
r        reset local min/max stats
t        reload theme file
```

## Offline Place Names

`gps-tui` can show the nearest populated place using offline GeoNames data. It
uses:

- `cities1000.txt`
- `countryInfo.txt`
- `admin1CodesASCII.txt`

Download them into `data/geonames`:

```sh
mkdir -p data/geonames
cd data/geonames
curl -LO https://download.geonames.org/export/dump/cities1000.zip
curl -LO https://download.geonames.org/export/dump/countryInfo.txt
curl -LO https://download.geonames.org/export/dump/admin1CodesASCII.txt
unzip -o cities1000.zip
cd ../..
```

Test a lookup:

```sh
python3 -m gps_tui.geonames --data-dir data/geonames 57.70716 11.96679
```

When the files are present, the main TUI loads them on startup and shows a
`Nearest` line in the GPS panel. GeoNames loading happens in the background so
the TUI can start immediately even on the Pi. The lookup is approximate:
country and region come from the nearest GeoNames city, not from border
polygons.

## gpsd Position Logger

`gps-tui-logger` is a Pi-side logging service that reads fixes from gpsd and
writes daily JSON Lines logs. It is intended to be the primary long-term logger;
the module's LOCUS logger can remain as a fallback.

Manual run:

```sh
python3 -m gps_tui.logger --log-dir ./logs
```

Default service log location:

```text
/var/log/gps/YYYY-MM-DD.jsonl
```

The logger:

- samples at 1 second intervals by default
- logs only `TPV` reports with a 2D or 3D fix and coordinates
- writes a `service_start` marker when it starts
- writes a `service_stop` marker on clean shutdown
- keeps the raw gpsd `TPV` report inside each fix record

Example log records:

```json
{"event":"service_start","type":"event","time":"2026-06-24T12:00:00.000Z"}
{"type":"fix","time":"2026-06-24T12:00:01.000Z","lat":57.7,"lon":11.9,"mode":3}
```

Install as a systemd service from the repo root:

```sh
scripts/install-gps-logger-service.sh
sudo systemctl start gps-tui-logger.service
systemctl status gps-tui-logger.service
```

Service configuration is written to:

```text
/etc/default/gps-tui-logger
```

## LOCUS Logger Commands

The Adafruit Ultimate GPS module has a LOCUS onboard logger. `gps-tui-device`
contains maintenance commands for that logger.

By default these commands use gpsd's client protocol:

```sh
gps-tui-device locus-status --device /dev/ttyUSB0
gps-tui-device locus-start --device /dev/ttyUSB0
gps-tui-device locus-stop --device /dev/ttyUSB0
gps-tui-device locus-dump --device /dev/ttyUSB0 --output locus.pmtklox
```

Internally, `gps-tui-device` opens a gpsd raw watch and sends PMTK commands with
gpsd `?DEVICE` hex writes. This lets gpsd keep ownership of the GPS device while
the tool captures `PMTKLOG` and `PMTKLOX` responses from the raw stream.

Direct serial is still available as a fallback:

```sh
gps-tui-device locus-status --transport serial --device /dev/ttyUSB0
```

The serial fallback requires `pyserial`:

```sh
python3 -m pip install pyserial
```

`locus-dump` writes raw `PMTKLOX` lines. GPX export is intentionally not enabled
yet; the raw dump should be captured from the real module first so the LOCUS
record layout can be verified without losing data. The default filename is
based on the dump time for now. Once LOCUS records are decoded, it should use
the first track point timestamp instead.

For this Adafruit/MTK module, observed LOCUS status values are:

```text
0 = logging
1 = stopped
```

The tested Adafruit MTK3333/PA1616D module reports logging type `1`, which is
FullStop / stop-when-full. Current evidence suggests that type is fixed in
firmware; `gps-tui` should not assume it can switch the logger to cyclic
overwrite mode. The safe archive workflow is dump, verify, erase with explicit
confirmation, then restart logging.

## gpsd Setup Notes

This app expects `gpsd` to already be running. A typical Pi setup for a USB GPS
is:

```sh
sudo apt install gpsd gpsd-clients
sudo systemctl enable --now gpsd
cgps
```

If `cgps` shows data, this app should be able to read the same stream.

## Theme

The default theme is `themes/btop-ish.toml`. It is intentionally simple and
keeps colors out of the rendering code.

Python 3.11+ can read TOML themes with the standard library. On Python 3.9 or
3.10, install `tomli` if you want custom theme loading:

```sh
python3 -m pip install tomli
```
