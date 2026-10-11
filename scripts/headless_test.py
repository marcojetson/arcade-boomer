#!/usr/bin/env python3
"""Headless test harness for Batocera pygame games.

    python3 headless_test.py path/to/game.pygame [--out DIR] [--scenario my_scenario.py] [--seconds 20]

Loads the game with SDL's dummy video/audio drivers *without* running its main(), then plays a
scenario, saves screenshots, measures update+render cost and prints a JSON report.

Expects the game module to expose: update(dt), render(), screen, and a Controls class whose
handle(event) maps pygame events to actions (the skill's game_template.pygame does). Optional:
SAVE_FILE (redirected to the output dir so real saves are untouched), current_screen.

Default scenario: screenshot the title, press START, play with random jumps, screenshot, measure
ms/frame over 300 frames, then let the game run on until it ends (or --seconds pass).

Custom scenario: a .py file defining `run(t)`; `t` provides
    t.game                  the loaded game module
    t.step(seconds, each_frame=None)   advance the game at 60 fps, optionally calling each_frame()
    t.key_down(key) / t.key_up(key) / t.tap(key)        keyboard events through Controls
    t.joy_down(button[, instance_id]) / t.joy_up(button[, instance_id])   raw-joystick buttons
    t.joy_axis(axis, value[, instance_id])              raw-joystick axis motion (e.g. a stick)
    t.shot(name)            save a 3x screenshot
    t.measure(frames=300, each_frame=None)              returns ms per update+render
    t.report                dict printed as JSON at the end
Notes: a "no fast renderer available" warning is normal under the dummy driver. If PNGs fail to
load or sounds are missing locally, your pygame lacks SDL_image/SDL_mixer — use pygame-ce to test.
"""
import argparse
import importlib.machinery
import importlib.util
import inspect
import json
import os
import random
import sys
import time
from types import SimpleNamespace


def load_game(path):
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    sys.dont_write_bytecode = True  # never leave __pycache__ next to a game that gets deployed
    sys.argv = [path, '--windowed']
    loader = importlib.machinery.SourceFileLoader('game_under_test', path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('game_under_test', loader))
    loader.exec_module(module)
    return module


def make_controls(game):
    controls_class = game.Controls
    parameters = [p for p in inspect.signature(controls_class.__init__).parameters if p != 'self']
    if not parameters:
        return controls_class()
    return controls_class(*(getattr(game, name) for name in parameters))


def build_toolkit(game, out_dir):
    import pygame
    controls = make_controls(game)
    report = {}
    image_extension = '.png' if pygame.image.get_extended() else '.bmp'

    def step(seconds, each_frame=None):
        for _ in range(int(seconds * 60)):
            if each_frame:
                each_frame()
            game.update(1 / 60)

    def send(event_type, **attributes):
        controls.handle(pygame.event.Event(event_type, **attributes))

    def shot(name):
        game.render()
        surface = game.screen
        big = pygame.transform.scale(surface, (surface.get_width() * 3, surface.get_height() * 3))
        path = os.path.join(out_dir, name + image_extension)
        pygame.image.save(big, path)
        report.setdefault('screenshots', []).append(path)

    def measure(frames=300, each_frame=None):
        start = time.perf_counter()
        for _ in range(frames):
            if each_frame:
                each_frame()
            game.update(1 / 60)
            game.render()
        return round((time.perf_counter() - start) / frames * 1000, 3)

    def tap(key):
        send(pygame.KEYDOWN, key=key)
        send(pygame.KEYUP, key=key)

    return SimpleNamespace(
        game=game, controls=controls, report=report, step=step, shot=shot, measure=measure, tap=tap,
        key_down=lambda key: send(pygame.KEYDOWN, key=key),
        key_up=lambda key: send(pygame.KEYUP, key=key),
        joy_down=lambda button, instance_id=999: send(pygame.JOYBUTTONDOWN, button=button, instance_id=instance_id, joy=0),
        joy_up=lambda button, instance_id=999: send(pygame.JOYBUTTONUP, button=button, instance_id=instance_id, joy=0),
        joy_axis=lambda axis, value, instance_id=999: send(pygame.JOYAXISMOTION, axis=axis, value=value, instance_id=instance_id, joy=0),
    )


def default_scenario(t, seconds):
    import pygame
    screen_name = lambda: getattr(t.game, 'current_screen', '?')
    t.report['screens'] = [screen_name()]
    t.shot('1-title')
    t.tap(pygame.K_RETURN)
    t.step(0.2)
    t.report['screens'].append(screen_name())

    def random_jumps():
        if random.random() < 0.04:
            t.tap(pygame.K_SPACE)

    t.step(3, random_jumps)
    t.shot('2-playing')
    t.report['ms_per_frame'] = t.measure(300, random_jumps)
    t.report['ms_per_frame_note'] = 'update+render on this machine; a Pi 4 is roughly 10-20x slower'
    first_screen = screen_name()
    for _ in range(int(seconds * 60)):
        if screen_name() != first_screen:
            break
        t.step(1 / 60)
    t.step(1.5)
    t.report['screens'].append(screen_name())
    t.shot('3-end')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('game')
    parser.add_argument('--out', default='headless-shots')
    parser.add_argument('--scenario', help='python file defining run(t)')
    parser.add_argument('--seconds', type=float, default=20, help='max seconds to wait for the run to end')
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    game = load_game(os.path.abspath(args.game))
    if hasattr(game, 'SAVE_FILE'):
        game.SAVE_FILE = os.path.join(out_dir, 'test-save.json')
    t = build_toolkit(game, out_dir)
    t.report['sounds_loaded'] = len(getattr(game, 'sounds', {}) or {})

    if args.scenario:
        scenario_loader = importlib.machinery.SourceFileLoader('scenario', os.path.abspath(args.scenario))
        scenario = importlib.util.module_from_spec(importlib.util.spec_from_loader('scenario', scenario_loader))
        scenario_loader.exec_module(scenario)
        scenario.run(t)
    else:
        default_scenario(t, args.seconds)
    print(json.dumps(t.report, indent=2, default=str))


if __name__ == '__main__':
    main()
