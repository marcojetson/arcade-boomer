#!/usr/bin/env python3
"""Install a pygame game folder onto a Batocera box over its network share.

    python3 deploy.py path/to/my-game --share /Volumes/share \
        --name "My Game" --desc "One paragraph for the menu." --image screenshot.png [--dry-run]

The folder must contain <folder-name>.pygame. The script:
  * copies it to <share>/roms/<system>/<folder-name>/ (default system: pygame), with plain
    file copies (no macOS extended attributes, which SMB shares reject), skipping __pycache__,
    .DS_Store, ._* files and *-save.json — the box's own save file is left untouched
  * copies --image to <share>/roms/<system>/images/<folder-name>.png
  * adds or updates the game's entry in roms/<system>/gamelist.xml after saving a backup copy
    locally (--backup-dir, default: current directory)
  * removes stray ._* files and verifies every copied file byte for byte
EmulationStation may need "Update gamelists" before a brand-new game appears.
"""
import argparse
import filecmp
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ElementTree

SKIPPED_NAMES = {'__pycache__', '.DS_Store'}


def is_skipped(name):
    return name in SKIPPED_NAMES or name.startswith('._') or name.endswith('-save.json')


def files_to_copy(source_dir):
    for root, directories, files in os.walk(source_dir):
        directories[:] = [d for d in directories if not is_skipped(d)]
        for name in files:
            if not is_skipped(name):
                path = os.path.join(root, name)
                yield path, os.path.relpath(path, source_dir)


def copy_plain(source, destination, dry_run):
    print(('would copy ' if dry_run else 'copy ') + destination)
    if not dry_run:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(source, destination)  # contents only: SMB shares reject macOS xattrs


def update_gamelist(gamelist_path, slug, fields, backup_dir, dry_run):
    entry_path = f'./{slug}/{slug}.pygame'
    if os.path.exists(gamelist_path):
        tree = ElementTree.parse(gamelist_path)
        backup = os.path.join(backup_dir, f'gamelist.backup-{time.strftime("%Y%m%d-%H%M%S")}.xml')
        counter = 1
        while os.path.exists(backup):  # never overwrite an earlier (possibly pristine) backup
            backup = os.path.join(backup_dir, f'gamelist.backup-{time.strftime("%Y%m%d-%H%M%S")}-{counter}.xml')
            counter += 1
        if not dry_run:
            shutil.copyfile(gamelist_path, backup)
        print(('would back up ' if dry_run else 'backed up gamelist to ') + backup)
    else:
        tree = ElementTree.ElementTree(ElementTree.Element('gameList'))
    root = tree.getroot()
    game = next((g for g in root.findall('game') if (g.findtext('path') or '').strip() == entry_path), None)
    action = 'update' if game is not None else 'add'
    if game is None:
        game = ElementTree.SubElement(root, 'game')
        ElementTree.SubElement(game, 'path').text = entry_path
    for tag, value in fields.items():
        if value is None:
            continue
        element = game.find(tag)
        if element is None:
            element = ElementTree.SubElement(game, tag)
        element.text = str(value)
    print(f'{"would " if dry_run else ""}{action} gamelist entry {entry_path}')
    if not dry_run:
        if hasattr(ElementTree, 'indent'):
            ElementTree.indent(tree, space='\t')
        tree.write(gamelist_path, encoding='utf-8', xml_declaration=True)


def remove_apple_double_files(directory, dry_run):
    for root, _, files in os.walk(directory):
        for name in files:
            if name.startswith('._'):
                print(('would remove ' if dry_run else 'remove ') + os.path.join(root, name))
                if not dry_run:
                    os.remove(os.path.join(root, name))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('game_folder')
    parser.add_argument('--share', required=True, help='mounted Batocera share, e.g. /Volumes/share')
    parser.add_argument('--system', default='pygame')
    parser.add_argument('--name')
    parser.add_argument('--desc')
    parser.add_argument('--image', help='PNG screenshot for the menu')
    parser.add_argument('--genre')
    parser.add_argument('--players')
    parser.add_argument('--developer')
    parser.add_argument('--backup-dir', default=os.getcwd())
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    source_dir = os.path.abspath(args.game_folder)
    slug = os.path.basename(source_dir.rstrip('/'))
    if not os.path.isfile(os.path.join(source_dir, slug + '.pygame')):
        sys.exit(f'{source_dir} must contain {slug}.pygame')
    system_dir = os.path.join(args.share, 'roms', args.system)
    if not os.path.isdir(system_dir):
        sys.exit(f'{system_dir} not found — is the share mounted? (the box may be asleep or off)')

    destination_dir = os.path.join(system_dir, slug)
    copied = []
    for source, relative in files_to_copy(source_dir):
        destination = os.path.join(destination_dir, relative)
        copy_plain(source, destination, args.dry_run)
        copied.append((source, destination))

    image_entry = None
    if args.image:
        image_destination = os.path.join(system_dir, 'images', slug + '.png')
        copy_plain(os.path.abspath(args.image), image_destination, args.dry_run)
        copied.append((os.path.abspath(args.image), image_destination))
        image_entry = f'./images/{slug}.png'

    fields = {'name': args.name or slug, 'desc': args.desc, 'image': image_entry, 'genre': args.genre,
              'players': args.players, 'developer': args.developer}
    update_gamelist(os.path.join(system_dir, 'gamelist.xml'), slug, fields, args.backup_dir, args.dry_run)
    remove_apple_double_files(system_dir, args.dry_run)

    if args.dry_run:
        print(f'dry run: {len(copied)} files would be installed to {destination_dir}')
        return
    mismatches = [d for s, d in copied if not filecmp.cmp(s, d, shallow=False)]
    if mismatches:
        sys.exit('copy verification failed for: ' + ', '.join(mismatches))
    print(f'installed {len(copied)} files to {destination_dir}, all verified')


if __name__ == '__main__':
    main()
