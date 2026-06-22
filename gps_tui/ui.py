from __future__ import annotations

import curses
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from .model import GpsState, Satellite
from .theme import Theme, load_theme


COLOR_NAMES = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
    "bright_black": curses.COLOR_BLACK,
    "bright_red": curses.COLOR_RED,
    "bright_green": curses.COLOR_GREEN,
    "bright_yellow": curses.COLOR_YELLOW,
    "bright_blue": curses.COLOR_BLUE,
    "bright_magenta": curses.COLOR_MAGENTA,
    "bright_cyan": curses.COLOR_CYAN,
    "bright_white": curses.COLOR_WHITE,
}


class Palette:
    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.pairs: dict[str, int] = {}

    def init(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        names = [
            "foreground",
            "muted",
            "border",
            "title",
            "accent",
            "ok",
            "warn",
            "bad",
            "bar_low",
            "bar_mid",
            "bar_high",
            "used",
        ]
        for index, name in enumerate(names, start=1):
            curses.init_pair(index, _color_number(self.theme.color(name)), -1)
            self.pairs[name] = index

    def attr(self, name: str, extra: int = 0) -> int:
        pair = self.pairs.get(name, self.pairs.get("foreground", 0))
        return curses.color_pair(pair) | extra


def run_ui(
    stdscr: Any,
    state: GpsState,
    reports: Queue[dict[str, Any]],
    theme_path: Path | None,
    refresh_seconds: float,
) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(max(50, int(refresh_seconds * 1000)))

    theme = load_theme(theme_path)
    palette = Palette(theme)
    palette.init()
    paused = False

    while True:
        if not paused:
            _drain_reports(reports, state)

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("p"), ord("P")):
            paused = not paused
        elif key in (ord("r"), ord("R")):
            state.reset_stats()
        elif key in (ord("t"), ord("T")):
            theme = load_theme(theme_path)
            palette = Palette(theme)
            palette.init()

        _draw(stdscr, state, theme, palette, paused)


def _drain_reports(reports: Queue[dict[str, Any]], state: GpsState) -> None:
    from .gpsd import apply_report

    while True:
        try:
            report = reports.get_nowait()
        except Empty:
            return
        apply_report(state, report)


def _draw(stdscr: Any, state: GpsState, theme: Theme, palette: Palette, paused: bool) -> None:
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    if height < 14 or width < 52:
        _add(stdscr, 0, 0, "gps-tui needs at least 52x14", palette.attr("warn"))
        stdscr.refresh()
        return

    vertical = width >= 100
    status_h = 1
    work_h = height - status_h

    if vertical:
        info_w = max(44, min(58, width // 2))
        info = (0, 0, work_h, info_w)
        sats = (0, info_w, work_h, width - info_w)
    else:
        info_h = max(10, min(14, work_h // 2))
        info = (0, 0, info_h, width)
        sats = (info_h, 0, work_h - info_h, width)

    _panel(stdscr, *info, "GPS", palette)
    _panel(stdscr, *sats, "SATELLITES", palette)
    _draw_info(stdscr, info, state, theme, palette)
    _draw_satellites(stdscr, sats, state, theme, palette)
    _draw_status(stdscr, height - 1, width, state, palette, paused)
    stdscr.refresh()


def _panel(stdscr: Any, y: int, x: int, height: int, width: int, title: str, palette: Palette) -> None:
    attr = palette.attr("border")
    if height < 2 or width < 2:
        return
    _add(stdscr, y, x, "╭" + "─" * max(0, width - 2) + "╮", attr)
    for row in range(y + 1, y + height - 1):
        _add(stdscr, row, x, "│", attr)
        _add(stdscr, row, x + width - 1, "│", attr)
    _add(stdscr, y + height - 1, x, "╰" + "─" * max(0, width - 2) + "╯", attr)
    _add(stdscr, y, x + 2, f" {title} ", palette.attr("title", curses.A_BOLD))


def _draw_info(
    stdscr: Any,
    rect: tuple[int, int, int, int],
    state: GpsState,
    theme: Theme,
    palette: Palette,
) -> None:
    y, x, height, width = rect
    fix = state.fix
    inner_w = width - 4
    row = y + 2

    fix_attr = palette.attr("ok" if fix.mode >= 3 else "warn" if fix.mode == 2 else "bad", curses.A_BOLD)
    _kv(stdscr, row, x + 2, inner_w, f"{theme.symbol('fix')} Fix", fix.mode_label.upper(), fix_attr, palette)
    row += 1
    _kv(stdscr, row, x + 2, inner_w, "Latitude", _coord(fix.lat, "N", "S"), palette.attr("foreground"), palette)
    row += 1
    _kv(stdscr, row, x + 2, inner_w, "Longitude", _coord(fix.lon, "E", "W"), palette.attr("foreground"), palette)
    row += 1
    if state.location is not None and height >= 11:
        _kv(
            stdscr,
            row,
            x + 2,
            inner_w,
            "Nearest",
            f"{state.location.name} ({state.location.distance_text})",
            palette.attr("accent"),
            palette,
        )
        row += 1
    _kv(stdscr, row, x + 2, inner_w, f"{theme.symbol('accuracy')} Accuracy", _accuracy(fix), _accuracy_attr(fix.eph_m, palette), palette)
    row += 1
    _kv(stdscr, row, x + 2, inner_w, f"{theme.symbol('altitude')} Altitude", _meters(fix.alt_m), palette.attr("foreground"), palette)
    row += 1
    _kv(stdscr, row, x + 2, inner_w, f"{theme.symbol('speed')} Speed", _kmh(fix.speed_kmh), palette.attr("foreground"), palette)

    if height >= 13:
        row += 1
        _kv(stdscr, row, x + 2, inner_w, "Track", _degrees(fix.track_deg), palette.attr("foreground"), palette)
        row += 1
        _kv(stdscr, row, x + 2, inner_w, "Climb", _mps(fix.climb_mps), palette.attr("foreground"), palette)
        row += 1
        _kv(stdscr, row, x + 2, inner_w, f"{theme.symbol('time')} UTC", fix.time or "--", palette.attr("muted"), palette)

    if height >= 16:
        row += 1
        _kv(stdscr, row, x + 2, inner_w, "Best accuracy", _meters(state.min_eph_m), palette.attr("accent"), palette)
        row += 1
        _kv(stdscr, row, x + 2, inner_w, "Max speed", _kmh(state.max_speed_kmh), palette.attr("accent"), palette)


def _draw_satellites(
    stdscr: Any,
    rect: tuple[int, int, int, int],
    state: GpsState,
    theme: Theme,
    palette: Palette,
) -> None:
    y, x, height, width = rect
    sky = state.sky
    inner_w = width - 4
    header = (
        f"{theme.symbol('satellite')} visible {sky.n_sat if sky.n_sat is not None else len(sky.satellites)}"
        f"  used {sky.u_sat if sky.u_sat is not None else _used_count(sky.satellites)}"
        f"  HDOP {_number(sky.hdop, 1)}  VDOP {_number(sky.vdop, 1)}  PDOP {_number(sky.pdop, 1)}"
    )
    _add(stdscr, y + 2, x + 2, header[:inner_w], palette.attr("foreground", curses.A_BOLD))

    chart_y = y + 4
    max_rows = max(0, height - 6)
    if max_rows == 0:
        return

    sats = sky.satellites[:max_rows]
    if not sats:
        _add(stdscr, chart_y, x + 2, "Waiting for sky view data", palette.attr("muted"))
        return

    label_w = 5
    value_w = 8
    bar_w = max(6, inner_w - label_w - value_w - 4)
    for index, sat in enumerate(sats):
        row = chart_y + index
        signal = sat.signal_db or 0.0
        filled = min(bar_w, max(0, int(round((signal / 60.0) * bar_w))))
        bar = "█" * filled + "░" * (bar_w - filled)
        attr = _bar_attr(signal, sat.used, palette)
        label_attr = palette.attr("used" if sat.used else "muted", curses.A_BOLD if sat.used else 0)
        _add(stdscr, row, x + 2, f"{sat.label:<{label_w}}", label_attr)
        _add(stdscr, row, x + 2 + label_w, bar, attr)
        _add(stdscr, row, x + 2 + label_w + bar_w + 1, _sat_meta(sat)[:value_w + 3], palette.attr("muted"))


def _draw_status(stdscr: Any, y: int, width: int, state: GpsState, palette: Palette, paused: bool) -> None:
    age = "--"
    if state.last_update is not None:
        age = f"{(datetime.now(timezone.utc) - state.last_update).total_seconds():.0f}s"
    mode = "PAUSED" if paused else "LIVE"
    status = f" {mode}  source {state.source}  {state.message}  age {age}  q quit  p pause  r reset  t reload-theme "
    attr = palette.attr("muted" if paused else "foreground", curses.A_REVERSE)
    _add(stdscr, y, 0, status.ljust(width)[:width], attr)


def _kv(stdscr: Any, y: int, x: int, width: int, label: str, value: str, value_attr: int, palette: Palette) -> None:
    label_width = min(18, max(10, width // 3))
    _add(stdscr, y, x, label[:label_width].ljust(label_width), palette.attr("muted"))
    _add(stdscr, y, x + label_width + 1, value[: max(0, width - label_width - 1)], value_attr)


def _add(stdscr: Any, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        height, width = stdscr.getmaxyx()
        if y < 0 or y >= height or x >= width:
            return
        stdscr.addnstr(y, max(0, x), text, max(0, width - max(0, x)), attr)
    except curses.error:
        pass


def _coord(value: float | None, positive: str, negative: str) -> str:
    if value is None:
        return "--"
    hemi = positive if value >= 0 else negative
    return f"{abs(value):.7f}° {hemi}"


def _accuracy(fix: Any) -> str:
    parts = []
    if fix.eph_m is not None:
        parts.append(f"H {_meters(fix.eph_m)}")
    if fix.epv_m is not None:
        parts.append(f"V {_meters(fix.epv_m)}")
    if fix.sep_m is not None:
        parts.append(f"3D {_meters(fix.sep_m)}")
    return "  ".join(parts) if parts else "--"


def _accuracy_attr(eph: float | None, palette: Palette) -> int:
    if eph is None:
        return palette.attr("muted")
    if eph <= 5:
        return palette.attr("ok")
    if eph <= 15:
        return palette.attr("warn")
    return palette.attr("bad")


def _bar_attr(signal: float, used: bool, palette: Palette) -> int:
    if used:
        return palette.attr("used", curses.A_BOLD)
    if signal >= 38:
        return palette.attr("bar_high")
    if signal >= 22:
        return palette.attr("bar_mid")
    return palette.attr("bar_low")


def _sat_meta(sat: Satellite) -> str:
    signal = "--" if sat.signal_db is None else f"{sat.signal_db:>4.1f}"
    used = "used" if sat.used else "seen"
    return f"{signal}dB {used}"


def _meters(value: float | None) -> str:
    return "--" if value is None else f"{value:.1f} m"


def _mps(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f} m/s"


def _kmh(value: float | None) -> str:
    return "--" if value is None else f"{value:.1f} km/h"


def _degrees(value: float | None) -> str:
    return "--" if value is None else f"{value:.1f}°"


def _number(value: float | None, digits: int) -> str:
    return "--" if value is None else f"{value:.{digits}f}"


def _used_count(satellites: list[Satellite]) -> int:
    return sum(1 for sat in satellites if sat.used)


def _color_number(name: str) -> int:
    normalized = name.lower()
    base = COLOR_NAMES.get(normalized, curses.COLOR_WHITE)
    if normalized.startswith("bright_") and getattr(curses, "COLORS", 0) >= 16:
        return base + 8
    return base
