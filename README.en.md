# Spool Manager

[Français](README.md) | **English**

Filament inventory coupled with **Snapmaker Orca**. You record the spools on your shelf;
each time you slice, the app reads the grams used and deducts them from the right spool.

Built for the **Snapmaker U1** and its 4 filament slots, it also works with a
single-extruder printer (the number of slots is configurable).

![Dashboard](docs/apercu/tableau-de-bord.png)

## How it works

Snapmaker Orca can run a script when it writes a G-code file. That script reads the
statistics embedded in the G-code and drops a small file into an inbox. The app, sitting
in the notification area, picks it up, identifies the matching spools, and updates stock.

```
Orca export  ->  hook  ->  inbox  ->  application  ->  stock updated
```

When the hook runs depends on the printer. On a **Bambu** (A1 Mini, X1…), Orca runs it
as soon as you slice. On the **Snapmaker U1**, Orca only runs it when you export G-code
(`File → Export → Export G-code`). The app also watches Orca’s temp folder, so a U1
slice is deducted as soon as the preview is ready.

The hook never modifies your G-code and cannot fail a slice: on error it writes to its
log and exits normally.

G-code parsing is locked to two real Snapmaker Orca 2.3.5 exports for the U1, one colour
and two colours with a purge tower, kept in `tests/fixtures`. Grams are cross-checked
against the volume and density Orca reports. Purge filament from tool changes is already
included in each filament’s grams: nothing is left out of the deduction.

### Automatic spool matching

For each filament in the slice, the app scores candidate spools:

| Signal | Weight |
| --- | --- |
| Spool assigned to the same printer slot | very strong |
| Identical Orca filament preset | strong |
| Identical colour | medium |
| Identical brand | weak |
| Different material | eliminatory |

Deduction is applied **without confirmation** when one spool clearly outranks the others.
On ambiguity, missing material, or insufficient stock, the slice goes to a “to review”
queue and nothing is deducted until you decide. Every deduction can be undone from the
history.

Filling in the 4 slots on the **U1 printer** tab is what makes matching almost certain:
the G-code says which slot was used.

## Installation

### Windows installer (recommended)

Download `SpoolManager-1.0.0-Setup.exe` from the [GitHub releases](https://github.com/Tellus75/spool_manager_U1/releases)
and run it. The app installs into your Windows user profile, with no administrator
rights, and creates a Start menu shortcut.

On first launch, go to **Settings** and click **Install the hook on all my profiles**,
with Snapmaker Orca closed.

### From the executable (no installer)

1. Copy the `SpoolManager` folder wherever you like, for example under `C:\Program Files`.
2. Run `SpoolManager.exe`.
3. Go to **Settings** and click **Install the hook on all my profiles**, with Snapmaker
   Orca closed.

No Python is required.

### From source

```powershell
pip install -r requirements.txt
python run.py
```

To rebuild the executable and the installer:

```powershell
pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File tools/build_installer.ps1
```

The installer then lands in `installer\output`. A Git tag such as `v1.0.1` also
triggers a GitHub Actions build.

The PyInstaller output is in `dist/SpoolManager`.

## Wiring the hook in Orca

The **Settings** screen installs the hook automatically, but Orca has a limitation:
post-processing scripts belong to the **print profile**, not to a global setting. There
is nowhere to declare them once and for all.

The app therefore writes the hook into all of your **user** print profiles. It does not
touch system profiles, which Orca rewrites on every update. If you slice with a system
profile (for example `0.20 Standard @Snapmaker U1`), duplicate it first in Orca with the
save icon next to the profile name, then come back and click **Refresh**.

Close Orca before installing the hook: Orca rewrites its profiles on exit and would
undo the change. The app warns you if Orca is open.

For a manual install, copy the command shown in Settings and paste it in Orca under
**Print settings > Others > Post-processing scripts**.

### Safety net

If a profile has no hook, enable **folder watching** in Settings and point it at the
folder where you export G-code. The app detects new files and deducts them the same way.
A file already seen is never counted twice, and files present at startup are ignored so
old prints are not deducted retroactively.

## Usage

### Recording your spools

From **Add a spool**, **Import a profile…** pulls brand, material, density and price
from the filament presets in your Orca install, so you do not have to retype them.

Two weights are asked for, and they are not the same thing. **Net weight at purchase**
is the reference for the fill gauge. **Tare** is the empty spool weight, used when you
weigh a spool.

Linking the **Orca preset** to the spool greatly improves automatic matching if you do
not keep the printer slots up to date.

### Recalibrating by weighing

Theoretical deduction always drifts: purges, failed prints, leftover filament. Put the
whole spool on a scale, enter the displayed weight in **Weigh…**, and the app subtracts
the tare to recompute what is left. The weighing is authoritative and the delta is
stored as a movement, so history stays consistent.

### History and undo

Each slice is listed with a per-spool breakdown. **Undo deduction** restores exactly the
grams that were removed. Nothing is ever overwritten: a spool’s remaining weight is
always the sum of its movements, which keeps history auditable.

## Where your data lives

Everything is in `%APPDATA%\SpoolManager`:

| Item | Contents |
| --- | --- |
| `spoolmanager.db` | SQLite database: spools, slices, movements |
| `inbox` | slices sent by the hook, waiting to be processed |
| `inbox-traites` | slices already ingested, kept for diagnostics |
| `logs\orca_hook.log` | hook log, check this if a slice never arrives |

Backing up `spoolmanager.db` is enough to back up your whole inventory.

## If a slice is not deducted

1. On the U1: Spool Manager must be running during the slice (it reads the temporary
   G-code). If the app was closed, export the G-code or start it afterwards.
2. Is the app running? It should stay in the notification area. Otherwise slices are
   picked up on the next start; nothing is lost.
3. Is the print profile you used checked in Settings?
4. What does `logs\orca_hook.log` say? A line is written each time the hook runs
   (Bambu on slice, U1 on export).
5. Does the `inbox` folder contain unconsumed files?

## Checking G-code parsing

Orca’s header format can change between versions. To check that a slice is read
correctly, without deducting anything:

```powershell
python tools/validate_gcode.py "C:\path\to\part.gcode"
python tools/validate_gcode.py                 # uses the most recent G-code
python tools/validate_gcode.py part.gcode --match   # also simulates matching
```

The tool prints grams per slot, cross-checks the reported figures against those it
recomputes (sum of filaments, volume times density), and flags any unexpected
`filament*` key. A report with no inconsistency means automatic deduction will use the
right numbers.

## Development

```powershell
python -m pytest tests -q          # full suite
python tools/check_orca.py         # Orca integration diagnostic
python tools/validate_gcode.py     # parser check on a real G-code
python tools/make_fixture.py a.gcode tests/fixtures/b.gcode  # lightweight test fixture
python tools/render_preview.py     # capture each tab into docs/apercu
```

UI tests run off-screen and do not open any window.

### Layout

| File | Role |
| --- | --- |
| `spoolmanager/gcode_parser.py` | read statistics from Orca G-code |
| `spoolmanager/matching.py` | score and choose the spool |
| `spoolmanager/inventory.py` | stock movements, deduction, undo |
| `spoolmanager/orca.py` | filament presets and hook install |
| `spoolmanager/watcher.py` | inbox and folder watching |
| `spoolmanager/hook_runner.py` | post-processing script logic |
| `hook/orca_hook.py` | wrapper called by Orca |
