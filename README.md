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

## Options

```text
--host HOST           gpsd host, default localhost
--port PORT           gpsd port, default 2947
--simulate            use generated GPS data instead of gpsd
--theme PATH          theme TOML file, default themes/btop-ish.toml
--refresh SECONDS     screen refresh interval, default 0.5
```

## Keys

```text
q        quit
p        pause/resume updates
r        reset local min/max stats
t        reload theme file
```

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
