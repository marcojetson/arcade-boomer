---
name: arcade-boomer
description: Build, port, test and install games that run on a Batocera retro-gaming box (Raspberry Pi 4 or similar) through Batocera's built-in "pygame" system. Use this whenever the user wants a game on their Batocera / arcade cabinet / retro handheld / Raspberry Pi emulation setup, wants to port a browser/HTML/JS or other game so it runs there, mentions .pygame files, roms/pygame, EmulationStation gamelists, arcade sticks and buttons in pygame, or complains that an HTML game is too slow on Batocera — even if they never say "pygame". Covers picking the right Batocera system, the folder layout, Pi-friendly rendering, controller/encoder input quirks, pre-rendered audio, headless testing and copying to the Batocera share.
---

# arcade-boomer: games for Batocera via pygame

Batocera ships a `pygame` system: any Python 3 script renamed to `.pygame` and placed in
`roms/pygame/<game>/` shows up in EmulationStation and runs fullscreen with the system's
Python + pygame (classic pygame 2.x, with SDL2, SDL_image and SDL_mixer). It is the most
practical way to run a custom 2D game natively on a Pi — HTML/browser ports run, but are
painfully slow there.

This skill bundles:

| Path | What it is |
|---|---|
| `assets/game_template.pygame` | A small but complete, runnable game skeleton with every Batocera lesson below baked in (display fitting, input dedupe, music, saves, pixel font). Start new games from it. |
| `scripts/synth.py` | Standard-library chiptune synth: tone sweeps, filtered noise, notes, pads, drums, WAV writer. Pre-renders sound effects and music at build time. |
| `scripts/headless_test.py` | Loads a `.pygame` file with SDL's dummy drivers, runs scenarios, saves screenshots, measures ms/frame. |
| `scripts/deploy.py` | Copies a game to the Batocera share, adds/updates its gamelist entry (with backup), keeps save files, verifies the copy. |

## 1. Pick the Batocera system first

Check what the user's box actually has: list `roms/` on the share (each folder is a system).

- **`pygame`** — preferred for custom games. Full Python, generated or loaded audio, SDL
  game-controller support, GPU-scaled fullscreen. Present on standard Batocera builds.
- **`lutro`** — a libretro core implementing a *subset* of the LÖVE (Lua) API. Plays sound
  files but cannot synthesise audio; good only for small Lua games.
- **`love`** — full LÖVE engine, not present on every build (it was absent on a Pi 4 box we
  checked). Only choose it if the folder exists.
- **`tic80` / `pico8`** — fantasy consoles with tight resolution/palette limits; pick them
  only if the game is designed for those limits.
- **`ports`** — shell-script launchers for native binaries; heavy setup, last resort.

## 2. Folder layout on Batocera

```
/userdata/roms/pygame/            (over the network: \\BATOCERA\share\roms\pygame)
├── gamelist.xml                  EmulationStation metadata for this system
├── images/<game>.png             screenshot shown in the menu
└── <game>/
    ├── <game>.pygame             the game: a Python 3 script
    ├── assets/                   sprites (PNG is fine)
    ├── sounds/                   WAV files
    └── <game>-save.json          written by the game at runtime
```

Gamelist entry (paths relative to `roms/pygame/`):

```xml
<game>
  <path>./<game>/<game>.pygame</path>
  <name>Pretty Name</name>
  <desc>One paragraph for the menu.</desc>
  <image>./images/<game>.png</image>
  <genre>Action</genre>
  <players>1</players>
</game>
```

New games may need "Update gamelists" (Main menu → Game settings) before they appear.
EmulationStation rewrites `gamelist.xml` itself, so make additive edits and keep a backup —
`scripts/deploy.py` does both.

## 3. Rendering that stays fast on a Pi 4

Python is the bottleneck on a Pi (roughly 10–20× slower than a modern laptop), not the GPU.
Design for it:

- **Draw to a small logical surface and let SDL scale it on the GPU**:
  `pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.SCALED | pygame.FULLSCREEN, vsync=1)`.
  SCALED uses SDL's renderer, so a 256×144 game costs the same as 256×144 even on a 4K TV.
  Never `pygame.transform.scale` the whole frame yourself each frame.
- **Fit the cabinet's screen shape** by reading `pygame.display.Info()` *before*
  `set_mode` and choosing the logical height from the aspect ratio (fixed width, so
  gameplay is identical on every screen; the extra height becomes scenery). Wrap
  `set_mode` in fallbacks: vsync can be refused; SCALED can fail on odd drivers.
- **Cache everything that doesn't change per frame**: text (render once per string/colour
  into a Surface, `functools.lru_cache`), sky gradients, glows, rotated sprites, translucent
  rectangles. Per-frame work should be `fill()` and `blit()` calls, not per-pixel loops.
- **Use `surface.fill(color, rect)` for pixel-art shapes**, `BLEND_RGB_ADD` blits for
  additive glows, and pre-made `set_alpha` surfaces for translucency.
- **Budget**: measure ms per frame with `scripts/headless_test.py`. Under ~1 ms on a laptop
  is comfortably 60 fps on a Pi 4; above ~3 ms, start caching.
- Hide the mouse: `pygame.mouse.set_visible(False)`.

## 4. Input: sticks, pads and keyboard encoders

Arcade cabinets arrive as SDL game controllers, raw joysticks, or keyboard encoders
(MAME layout). Map raw events to a few *actions* (jump / fire / directions / start / back) and
keep the mapping in one reconfigurable place so it can change without touching game logic.

- **SDL GameController API** (`from pygame._sdl2 import controller`) gives Batocera's
  configured mapping: A/B/X/Y, START, BACK, D-pad. Use it when `controller.is_controller(i)`.
  Wrap the import in `try` — fall back to raw joysticks if it's missing.
- **Ignore raw `JOY*` events from devices you opened as controllers** (compare
  `event.instance_id` with `pad.as_joystick().get_instance_id()`), or every press fires twice.
- **Many cheap "USB gamepad" arcade encoders are dual-mode and also emit keyboard events.**
  `controller.is_controller(i)` is False for them, so they run through the raw-joystick path —
  but they *additionally* synthesise key presses: shoving a stick up sends a `JOYAXISMOTION`
  **and** a `KEYDOWN K_UP`; a face button sends a `JOYBUTTONDOWN` **and** a letter key; START
  sends a `KEYDOWN K_RETURN`. If your keyboard fallback is mapped to actions, every cabinet
  input fires twice — and because the emulated keys' axis polarity can differ from the stick's
  (up emits `K_DOWN`), a stick appears to drive the *other* player in reverse. This is the
  classic "player 1 moves player 2" bug. **Fix: ignore keyboard events while real joysticks are
  connected** — `if pygame.joystick.get_count() == 0:` around the key mapping — so the fallback
  still serves desktops with no pad, but the cabinet is driven only by `JOY*` events.
- **Don't guess raw button numbers.** Cheap encoders vary wildly. A common D-input pad is
  X=0, A=1, B=2, Y=3, L=4, R=5, SELECT=8, START=9 (note: **not** the "0 = primary, ≥7 = start"
  guess); MAME-style encoders differ again. Ship a tiny **`input.json` next to the game**, read
  at launch, so buttons and axis polarity are remappable without a rebuild — and so a stubborn
  cabinet can be fixed on the spot:

  ```json
  {"1": {"invert": "",  "buttons": {"fire": 1, "weapon": 2, "shield": [0, 3], "start": 9, "back": 8}},
   "2": {"invert": "y", "buttons": {"fire": 1, "weapon": 2, "shield": [0, 3], "start": 9, "back": 8}}}
  ```

  Keys are 1-based player numbers; `invert` takes `x` and/or `y`; a button may map to a list of
  indices. `deploy.py` copies it like any other game file. Ignore a missing/malformed file.
- **Assign players by `event.instance_id`, not device index.** Two identical encoders share the
  same name *and* USB GUID, so only `instance_id` tells them apart. Build an
  `instance_id -> player` map when you `scan()` devices.
- **A physical press can still arrive twice** even from one device. Treat a repeat of the same
  action within ~80 ms as the same press, and track which inputs hold an action so "release"
  fires only when all of them let go. The template's `Controls` class does this.
- **Exit**: Batocera's own hotkey exit closes pygame games like any other system (confirmed on
  a Pi 4), so no extra work is needed. Still support Select+Start (BACK+START held) and Esc →
  `pygame.quit(); sys.exit()` as a fallback for setups without a hotkey configured and for
  desktop testing.
- **Hot-plug**: rescan devices on `JOYDEVICEADDED` / `JOYDEVICEREMOVED`.
- **No pause button in fast arcade games** — a shared Start button double-firing turns a
  pause into a trap, and arcade players don't expect one.
- Name buttons the way Batocera does ("A", "B", "START") in on-screen hints.

## 5. Audio: pre-render, don't synthesise at runtime

Pure-Python sample synthesis is fine on a laptop but takes many seconds on a Pi. Render all
sound effects and music to WAV **at build time** with `scripts/synth.py` (standard library
only), commit the WAVs, and load them with `pygame.mixer.Sound`.

- Initialise with `pygame.mixer.pre_init(22050, -16, 1, 512)` before `pygame.init()`.
  Mono 22 kHz keeps files small and latency low.
- **Music**: reserve channel 0 (`pygame.mixer.set_reserved(1)`) and loop a `Sound` on it.
  For tempo that rises with game speed, render a few takes at different BPM and switch
  seamlessly at loop boundaries with `Channel.queue(next_take)`. Render loops with
  *wrap-around* note tails so the seam is click-free (`synth.render_loop` does this).
- Browser-style mixes are quiet on a cabinet amp; apply one global boost (~3×) when writing
  WAVs so relative balance stays intact. Check peaks stay under 1.0.
- **Degrade gracefully**: some pygame builds have no mixer (`pygame.mixer` raises
  `NotImplementedError`). Wrap mixer calls so the game runs silently instead of crashing.

## 6. Saves and files

- Resolve paths from the script itself: `GAME_DIR = os.path.dirname(os.path.abspath(__file__))`.
  The working directory at launch isn't guaranteed.
- Save JSON next to the game (`<game>-save.json`); the roms share is writable. Wrap writes in
  `try/except OSError` so a read-only setup just doesn't save.
- Never ship `__pycache__/` (test runs create it next to the `.pygame` file).

## 7. Porting an HTML5 canvas game

Canvas games map cleanly onto pygame: keep the same function and constant names so future
changes can be mirrored between versions.

| Canvas / Web | pygame |
|---|---|
| `ctx.fillRect` | `surface.fill(color, rect)` |
| `ctx.drawImage` / sprite sheet frames | `blit`, `subsurface` per frame |
| `ctx.scale(-1, 1)` | `pygame.transform.flip` (cache it) |
| `ctx.rotate` | `pygame.transform.rotate(img, -degrees)` (pygame is counter-clockwise; cache by angle step) |
| `globalAlpha` | `surface.set_alpha` on a copy / cached surface |
| `globalCompositeOperation='lighter'` | `blit(..., special_flags=pygame.BLEND_RGB_ADD)` |
| `requestAnimationFrame` loop | `clock.tick(60)`; clamp `dt` to ≤ 1/30 |
| Web Audio oscillators | pre-rendered WAVs via `scripts/synth.py` |
| `localStorage` | JSON file in the game folder |
| touch / keyboard | actions via the `Controls` pattern |

Phone-portrait web layouts should become landscape for a cabinet; re-tune speeds if the
playfield width (and therefore reaction time) changes.

## 8. Test headlessly before touching the cabinet

```bash
python3 -m venv /tmp/pg && /tmp/pg/bin/pip install pygame-ce   # or pygame
/tmp/pg/bin/python scripts/headless_test.py path/to/<game>.pygame --out /tmp/shots
```

- Use **pygame-ce** locally if `pip install pygame` builds from source without SDL_image /
  SDL_mixer (newer Python versions): PNGs then fail to load and sounds are missing, which
  looks like a game bug but isn't. Batocera's pygame has both.
- The harness sets `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`, imports the game
  without running `main()`, plays scenarios, saves screenshots, prints ms/frame. A warning
  "no fast renderer available" is expected under the dummy driver.
- Write game-specific scenario files (a bot that plays, an edge case like a doubled Start
  press) and pass them with `--scenario`; see the harness docstring.
- Look at the screenshots — placeholder rectangles mean sprites didn't load.
- Run the game windowed on the desktop too: `python3 <game>.pygame --windowed`.

### Diagnosing input you can't see

When the bug only happens on the cabinet, you usually can't watch the screen and can't take it
over SSH. Ship a throwaway **input-probe game** (a second `<slug>.pygame` in `roms/pygame/`) that
**writes a log file into the game folder** — readable straight off the share afterwards:

- Log **every** event, not just the ones you expect: `pygame.event.event_name(event.type)` plus
  `event.dict`, prefixed with `pygame.time.get_ticks()`. The guilty event is often a type you
  didn't think to log (this is how the dual-mode encoder's emulated `KeyDown` was caught).
- Also print the device table (`get_name()`, `get_instance_id()`, `is_controller(index)`, USB
  GUIDs) and your `instance_id -> player` map.
- Write the **whole buffer at once** on each change rather than appending line by line — `open(...,'a')`
  writes over an SMB share can arrive out of order, which makes the log lie about what caused what.
- Ask the user for a *minimal* sequence (one stick, one button at a time) so cross-talk is obvious.
- Remove the probe's folder **and its gamelist entry** when done — a stale probe is a confusing
  extra game in the menu.

## 9. Install on the box

```bash
python3 scripts/deploy.py path/to/<game-folder> --share /Volumes/share \
    --name "Pretty Name" --desc "..." --image screenshot.png
```

It copies to `roms/pygame/<game>/` (skipping `__pycache__`, keeping the box's save file),
copies the menu image, adds or updates the gamelist entry after backing it up, removes
macOS `._*` files, and verifies every file. Use `--dry-run` first if unsure.

Copying by hand from a Mac: use `cp -X` (plain `cp -R` fails on SMB shares trying to copy
extended attributes, and a `&&` chain stops halfway). If the share disappears mid-session,
the box is probably asleep or off — ask the user rather than retrying.

## 10. What is still unverified

Say so when these matter rather than presenting them as fact:

- The exact pygame version per Batocera release (code to classic pygame 2.0+ APIs; avoid
  pygame-ce-only features).
