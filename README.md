# arcade-boomer

> *"Back in my day we didn't run our games in a web browser.
> We wrote them properly, rendered the music ahead of time, and we liked it."*

**arcade-boomer** is an agent skill that teaches AI coding agents how
to build, port, test and install custom games on a [Batocera](https://batocera.org)
retro-gaming box (Raspberry Pi arcade cabinets, handhelds, living-room emulation rigs)
through Batocera's built-in **pygame** system.

He's the old-timer you want looking over your shoulder: he knows that HTML games crawl on a Pi,
that your arcade stick shows up as three different kinds of device, why pressing Start
sometimes starts *and* pauses the game, why one joystick can secretly be driving *both*
players, and that you never ship `__pycache__` to a cabinet.

Born from porting a browser endless-runner to a Batocera arcade cabinet,
where the HTML version was too slow to play and the pygame version runs well.

## What's inside

| Path | What it does |
|---|---|
| [`SKILL.md`](SKILL.md) | The knowledge: choosing a Batocera system, folder and gamelist layout, Pi-friendly rendering, controller / joystick / keyboard-encoder input quirks, pre-rendered audio, saves, porting HTML canvas games, testing and installing. |
| [`assets/game_template.pygame`](assets/game_template.pygame) | A tiny but complete one-button game with everything a cabinet needs already wired up: screen fitting, GPU scaling, input with duplicate-press filtering, looping music, JSON saves, a 3x5 pixel font. Start new games from it. |
| [`scripts/synth.py`](scripts/synth.py) | Standard-library chiptune synth (tone sweeps, filtered noise, notes, pads, drums, seamless loops) that pre-renders sound effects and music to WAV. |
| [`scripts/headless_test.py`](scripts/headless_test.py) | Runs a `.pygame` game with no display or sound card, plays a scenario, saves screenshots and measures ms per frame. |
| [`scripts/deploy.py`](scripts/deploy.py) | Installs a game onto the Batocera network share: copies files, adds the menu image, adds or updates the gamelist entry (with backup), keeps the box's save file, verifies every byte. |

## Install

With the [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add marcojetson/arcade-boomer
```

Or by hand: the skill is just this folder. Copy or symlink it into your agent's skills
directory (for example `~/.agents/skills/arcade-boomer`). Agents that support the Agent Skills
format pick it up whenever you talk about Batocera, arcade cabinets, `.pygame` files or porting
a game to your Pi.

## Use the tools directly

You don't need an AI agent to use the scripts.

**Start a game from the template**

```bash
mkdir -p my-game/sounds
cp assets/game_template.pygame my-game/my-game.pygame
python3 my-game/my-game.pygame --windowed       # needs pygame (or pygame-ce) on your desktop
```

**Render sounds**

```bash
python3 scripts/synth.py --demo my-game/sounds   # writes jump, coin, explosion, music-loop
```

Or import it in your own build script; see the docstring in [`scripts/synth.py`](scripts/synth.py).

**Test without a screen**

```bash
python3 -m venv /tmp/pg && /tmp/pg/bin/pip install pygame-ce
/tmp/pg/bin/python scripts/headless_test.py my-game/my-game.pygame --out /tmp/shots
```

**Install on your Batocera box** (mount its share first, e.g. `smb://batocera/share`)

```bash
python3 scripts/deploy.py my-game --share /Volumes/share \
    --name "My Game" --desc "Jump the blocks." --image /tmp/shots/2-playing.png --dry-run
```

Drop `--dry-run` when it looks right, then run *Update gamelists* in Batocera's menu.

## Controls the template understands

| Action | Gamepad / arcade stick | Keyboard / MAME-style encoder |
|---|---|---|
| Main button | A, stick or D-pad up | Left Ctrl, Space, Up |
| Start | Start | 1, Enter |
| Quit | Batocera's hotkey exit, or Select + Start | Esc |

Keyboard input is ignored entirely while a real pad is connected: many cheap arcade encoders are
dual-mode and also emit emulated key presses, so trusting both would fire every cabinet input
twice. For two-player games, ship a small `input.json` beside the game to remap buttons and flip
axis polarity per player — see `SKILL.md` §4.

## Requirements

- On the Batocera box: nothing. Batocera ships Python 3 and pygame.
- On your computer: Python 3.9+ for the scripts; pygame or **pygame-ce** to run and test games.
  If `pip install pygame` builds from source without image/sound support (common on very new
  Python versions), use `pygame-ce`.

## Known unknowns

arcade-boomer is honest about what he hasn't seen yet: the exact pygame version shipped by each
Batocera release. The code sticks to classic pygame 2.0+ APIs to stay safe.

Tested so far on a Raspberry Pi 4 running Batocera. Reports from other boards are very welcome.

## Not affiliated

Batocera and pygame are their respective projects' trademarks; arcade-boomer is an
independent community project.
