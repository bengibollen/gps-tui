# Panel Ideas

This file tracks possible panels for `gps-tui`. Ideas here are not committed
features yet; they are a place to keep the direction visible while the core UI
evolves.

## Recommendations

Best next panels to build first:

1. **Fix Quality Panel**: gives the quickest read on whether the GPS data is
   actually trustworthy.
2. **Movement Panel**: useful immediately when the device is moving, and it
   builds on fields already available in `TPV`.
3. **Raw gpsd Messages Panel**: not glamorous, but very useful while testing
   against the real Pi and GPS unit.

Good second wave:

- **Sky Hemisphere View**: visually interesting and uses real `SKY` data.
- **GPS Timeline**: useful once we keep short in-memory history.
- **Device/Connection Panel**: useful if the app becomes something that stays
  open for long sessions.
- **GPS Module Management**: read logger data and configure module settings,
  once the exact GPS chipset/protocol is known.

Fun or later:

- **ASCII Map / Mapscii-Style Location View**
- **Signal History Panel**
- **Altitude Profile**

## 1. Sky Hemisphere View

Draw a top-down hemisphere showing satellite positions in the sky.

Concept:

- Use `SKY` report satellite fields from gpsd:
  - `az`: azimuth in degrees
  - `el`: elevation in degrees
  - `used`: whether the satellite is part of the current fix
  - `ss`: signal strength
- Render a circular sky plot:
  - center = directly overhead, 90 degrees elevation
  - outer ring = horizon, 0 degrees elevation
  - angle = azimuth
- Mark used satellites with a brighter/accent color.
- Optionally encode signal strength by color or symbol weight.

Rendering options:

- Start with plain ASCII or box drawing characters for portability.
- Try Unicode braille cells for higher-resolution plotting inside a terminal
  character grid.
- Keep a fallback mode for terminals/fonts where braille does not look good.

Open questions:

- Should north be fixed at the top, or should the plot rotate with current
  track/heading when moving?
- Should labels show PRN/SVID directly on the plot, or should the plot use
  compact markers with a legend?
- How much detail is useful on small SSH terminal sizes?

## 2. ASCII Map / Mapscii-Style Location View

Draw a simple text map centered on the current GPS position.

Concept:

- A fun, low-detail map panel rather than a navigation feature.
- Start at a large scale, roughly Scandinavia-wide.
- Keep the current position centered.
- Render coastlines and land/sea shape with ASCII, braille, or block
  characters.

Possible approaches:

- Static bundled low-resolution map data for Scandinavia.
- Very rough generated coastline outlines.
- Optional later integration with vector map data if the panel becomes more
  useful than decorative.

Initial scope:

- Scandinavia-scale view.
- Current position marker in the center.
- Basic latitude/longitude grid or labels if space allows.
- No routing, map downloads, geocoding, or online dependency.

Open questions:

- Should the map always stay Scandinavia-scale, or allow zoom presets later?
- Should this panel require bundled coastline data, or is a rough stylized map
  good enough for the first pass?
- Should it use braille cells for denser map detail?

## 3. Fix Quality Panel

Show a compact, opinionated summary of GPS fix quality.

Concept:

- Fix mode: no fix, 2D, 3D.
- Satellites visible and used.
- HDOP, VDOP, PDOP.
- Horizontal and vertical accuracy.
- Age of last update.
- Overall status: excellent, good, weak, poor, or no fix.

Recommendation:

- **Build early.** This is probably the most useful next panel because it helps
  decide whether the displayed coordinates are worth trusting.

## 4. Movement Panel

Show motion-related values from the current fix and session.

Concept:

- Current speed in km/h.
- Track/heading in degrees.
- Climb/descent in m/s.
- Max speed this session.
- Optional later: distance traveled, average moving speed, stopped time.

Recommendation:

- **Build early.** The current model already tracks some of this, and it will
  be useful as soon as the GPS is carried around or used in a vehicle.

## 5. Raw gpsd Messages Panel

Show recent gpsd reports and connection events.

Concept:

- Display latest raw or lightly formatted `TPV`, `SKY`, `DEVICE`, `WATCH`, and
  error reports.
- Toggleable debug view.
- Useful for checking what fields this specific GPS unit actually provides.

Recommendation:

- **Build early as a debug/help panel.** It will save time when testing on the
  real Raspberry Pi.

## 6. GPS Timeline

Show short history graphs for key values.

Concept:

- Accuracy over time.
- Speed over time.
- Altitude over time.
- Satellites used over time.

Recommendation:

- **Good second wave.** Needs in-memory history, but it would make the app feel
  much more alive and btop-like.

## 7. Compass / Heading View

Draw a compass rose based on GPS track.

Concept:

- Show cardinal directions.
- Highlight current track when moving.
- Warn or dim the view when speed is too low for reliable GPS heading.

Recommendation:

- **Useful, but not first.** GPS heading gets noisy while stationary, so this is
  best after movement/session handling is clearer.

## 8. Device / Connection Panel

Show gpsd and device health.

Concept:

- gpsd host and port.
- Device path if gpsd reports it.
- Last update age.
- Reconnect count.
- Data rate.
- Last error.

Recommendation:

- **Good second wave.** Especially useful if the app will run for long sessions
  over SSH.

## 9. Trip Session Panel

Track session-level stats.

Concept:

- Session start time.
- Elapsed time.
- Distance traveled.
- Moving/stopped time.
- Min/max altitude.
- Best/worst accuracy.

Recommendation:

- **Later.** Useful, but needs careful filtering so GPS jitter does not inflate
  distance while stationary.

## 10. Position Formats Panel

Show the current position in multiple coordinate formats.

Concept:

- Decimal degrees.
- Degrees/minutes/seconds.
- Optional later: UTM, Maidenhead locator, or plus codes.

Recommendation:

- **Small and easy.** Worth adding when there is space or a detail view.

## 11. Clock / GPS Time Panel

Show time-related GPS information.

Concept:

- GPS UTC time.
- Local time.
- Age of last fix.
- Optional later: PPS status if available.

Recommendation:

- **Small supporting panel.** Useful as part of a status/details layout rather
  than as one of the first major panels.

## 12. Altitude Profile

Show a scrolling altitude graph.

Concept:

- Keep a short history of altitude readings.
- Draw a sparkline or block graph.
- Show min/max altitude in the visible window.

Recommendation:

- **Later.** Simple once history exists, but not as important as accuracy and
  movement.

## 13. Signal History Panel

Show signal strength changes over time.

Concept:

- Per-satellite signal history.
- Sparkline rows or heatmap-style strips.
- Highlight satellites used in the fix.

Recommendation:

- **Later.** Could look excellent, but it needs more layout and history work.

## 14. Status Log Panel

Show recent app and GPS events.

Concept:

- gpsd connected/disconnected.
- Fix acquired/lost.
- 2D/3D fix transitions.
- Accuracy crossed threshold.
- Theme reloaded.

Recommendation:

- **Useful second wave.** It pairs well with the raw gpsd panel but should be
  more human-readable.

## 15. GPS Module Management

Read and configure module-level features such as EEPROM settings and onboard
logging.

Research notes:

- See [docs/adafruit-ultimate-gps-management.md](docs/adafruit-ultimate-gps-management.md)
  for Adafruit Ultimate GPS GNSS / LOCUS / PMTK details.

Concept:

- Read device identity, firmware version, and supported features.
- Inspect and change persistent settings stored in module EEPROM/flash.
- Read onboard logger contents.
- Clear logger storage after confirmation.
- Configure update rate, GNSS constellations, output messages, baud rate, and
  logging mode if the hardware supports it.

Important implementation note:

- gpsd is ideal for live position data, but module configuration and logger
  extraction may require direct serial access to the GPS device.
- The protocol depends on the GPS chipset. For example, u-blox modules use UBX
  binary messages, while other modules may use different vendor commands.
- The app should avoid changing persistent GPS settings until it can identify
  the module and confirm the intended operation.

Possible UI shape:

- A separate management screen rather than a normal dashboard panel.
- Read-only inspection first.
- Explicit confirmation before writes, logger erase, baud changes, or EEPROM
  saves.
- Clear status/result log for every command sent to the device.

Open questions:

- What exact GPS module/chipset is this? Module name, USB ID, or `gpsmon`
  output would help.
- Is the logger exposed through standard NMEA/vendor commands, u-blox UBX, or
  a separate vendor tool/protocol?
- Can gpsd and direct serial access safely coexist, or should the app stop gpsd
  while doing configuration?
- Which operations are actually needed first: read logger, clear logger,
  configure logging interval, configure update rate, or save settings?

Recommendation:

- **Treat as a separate feature track.** Start with read-only detection and
  capability reporting, then add logger download, then add carefully confirmed
  configuration writes.
