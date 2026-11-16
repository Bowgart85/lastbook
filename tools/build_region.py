#!/usr/bin/env python3
"""Build one region's detailed map from OpenStreetMap and put it into a Lastbook data folder.

  python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work --data ~/LastbookData
  python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work              # build only, install nothing
  python3 tools/build_region.py ... --gpkg region.gpkg --pbf region.osm.pbf                   # files already here: nothing is downloaded

For a region outside the US, where packaging/state_maps.py has no data. A region file names the two Geofabrik
downloads (the "free" GeoPackage and the raw .osm.pbf), a label and a short code. The steps:

  1 download   both files into the work folder, unless they are there or --gpkg / --pbf name them
  2 streets    tools/build_map.py         -> <work>/out/map.sqlite     roads, land, water, buildings, help points
  3 places     tools/build_places_osm.py  -> <work>/out/places.sqlite  places, postal codes, municipalities, districts
  4 install    with --data: the two files go to <data>/derived/geo/, what they replace moves to <work>/replaced-<time>/,
               the map's cached answers are cleared, and map-set.json is written so the app's own check of the
               library accepts the new map (engine/setup/install.py check_map).

The app must be closed while step 4 runs. Terrain, building heights, waterbody outlines beyond the street map's
own, and street addresses are not built here. The place finder is replaced, so US place names are no longer in it.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent))


def fetch(url, dest):
    if dest.exists():
        print('have', dest.name, f'{dest.stat().st_size / 1e6:.0f} MB', flush=True)
        return dest
    print('downloading', url, flush=True)
    part = dest.with_name(dest.name + '.part')
    req = urllib.request.Request(url, headers={'User-Agent': 'lastbook-build-region'})
    with urllib.request.urlopen(req, timeout=120) as r, open(part, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)
    part.replace(dest)
    print('got', dest.name, f'{dest.stat().st_size / 1e6:.0f} MB', flush=True)
    return dest


def gpkg_from(path, work):
    """The .gpkg itself: the one member of a Geofabrik zip, extracted once into the work folder."""
    if path.suffix != '.zip':
        return path
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.infolist() if m.filename.endswith('.gpkg')]
        if len(members) != 1:
            sys.exit(f'{path.name} holds {len(members)} .gpkg files; expected one')
        out = work / Path(members[0].filename).name
        if not out.exists() or out.stat().st_size != members[0].file_size:
            with z.open(members[0]) as src, open(out, 'wb') as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        return out


def run(*args):
    r = subprocess.run([sys.executable, '-B', *map(str, args)])
    if r.returncode:
        sys.exit(f'{Path(args[0]).name} failed ({r.returncode})')


def install(out, data, work, code):
    from engine.setup import install as setup_install
    geo = data / 'derived' / 'geo'
    if not (data / 'library-data' / 'catalog.json').is_file():
        sys.exit(f'{data} is not a Lastbook data folder (no library-data/catalog.json)')
    geo.mkdir(parents=True, exist_ok=True)
    kept = work / time.strftime('replaced-%Y%m%d-%H%M%S')
    stale = [geo / n for n in ('map.sqlite', 'places.sqlite', 'socal-cells.json', 'tilecache')]
    stale += [geo / (n + side) for n in ('map.sqlite', 'places.sqlite') for side in setup_install.SQLITE_SIDES]
    stale.append(data / 'map-set.json')
    for p in stale:
        if p.exists():
            kept.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(kept / p.name))
    for name in ('map.sqlite', 'places.sqlite'):
        shutil.copy2(out / name, geo / name)
    files = {rel: (data / rel).stat().st_size for rel in setup_install.map_files(data) if rel != 'map-set.json'}
    (data / 'map-set.json').write_text(json.dumps({'name': code, 'files': files}, indent=1), encoding='utf-8')
    setup_install.check_map(data)
    print('installed in', geo, '· replaced files kept in', kept if kept.exists() else '(nothing was replaced)', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('region', help='a region file such as tools/regions/hessen.json')
    ap.add_argument('--work', required=True, help='folder for downloads and built files (several GB for a German state)')
    ap.add_argument('--data', help='Lastbook data folder to install into; without it the map is only built')
    ap.add_argument('--gpkg', help='a Geofabrik "free" .gpkg or .gpkg.zip already on this computer')
    ap.add_argument('--pbf', help='the region\'s .osm.pbf (or .osm) already on this computer')
    ap.add_argument('--no-boundaries', action='store_true', help='skip postal codes, municipalities and districts (no .osm.pbf, no osmium needed)')
    a = ap.parse_args()
    region = json.loads(Path(a.region).read_text(encoding='utf-8'))
    work = Path(a.work).expanduser().resolve()
    out = work / 'out'
    out.mkdir(parents=True, exist_ok=True)

    gpkg = Path(a.gpkg).expanduser() if a.gpkg else fetch(region['gpkg_url'], work / region['gpkg_url'].rsplit('/', 1)[1])
    as_of = time.strftime('%Y-%m-%d', time.gmtime(gpkg.stat().st_mtime))
    gpkg = gpkg_from(gpkg, work)
    pbf = None
    if not a.no_boundaries:
        try:
            import osmium  # noqa: F401
        except ImportError:
            sys.exit('Postal codes and boundaries need the osmium package (pip install osmium), or pass --no-boundaries.')
        pbf = Path(a.pbf).expanduser() if a.pbf else fetch(region['pbf_url'], work / region['pbf_url'].rsplit('/', 1)[1])

    run(TOOLS / 'build_map.py', gpkg, out / 'map.sqlite', '--source', region['source'], '--as-of', as_of)
    places = [TOOLS / 'build_places_osm.py', '--map', out / 'map.sqlite', '--out', out / 'places.sqlite', '--label', region['label'],
              '--levels', region.get('admin_levels', '6,8')]
    run(*places, *(['--pbf', pbf] if pbf else []))
    for name in ('map.sqlite', 'places.sqlite'):
        print(name, f'{(out / name).stat().st_size / 1e6:.1f} MB', flush=True)
    if a.data:
        install(out, Path(a.data).expanduser().resolve(), work, region['code'])


if __name__ == '__main__':
    main()
