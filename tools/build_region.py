#!/usr/bin/env python3
"""Build a detailed map of one or more regions from OpenStreetMap and put it into a Lastbook data folder.

  python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work --data ~/LastbookData
  python3 tools/build_region.py tools/regions/hessen.json tools/regions/bayern.json --work ... --data ...   # one map of both
  python3 tools/build_region.py --geofabrik europe/france/alsace:Alsace --work ... --data ...               # no region file
  python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work                            # build only
  python3 tools/build_region.py ... --gpkg region.gpkg --pbf region.osm.pbf     # one region, files already here

For regions outside the US, where packaging/state_maps.py has no data. A region is two Geofabrik downloads: the
"free" GeoPackage and the raw .osm.pbf. A region file names them with a label and a short code; --geofabrik
PATH:LABEL works them out from the region's path on download.geofabrik.de. Geofabrik offers the GeoPackage only
for regions below a size limit: a large country is built from its parts (Germany from its 16 states, all in
tools/regions/).

  1 download   both files of each region into the work folder, unless they are already there
  2 streets    tools/build_map.py         -> <work>/out/map.sqlite     roads, land, water, buildings, help points
  3 places     tools/build_places_osm.py  -> <work>/out/places.sqlite  places, postal codes, municipalities, districts
  4 terrain    with --terrain: tools/fetch_copernicus_dem.py and tools/build_terrain.py -> <work>/out/terrain.sqlite
               relief, contour lines, spot heights and the 3D view for the box the streets fall in, from
               Copernicus DEM GLO-30 (needs numpy and tifffile; imagecodecs too if a file will not open). With
               --data, the data folder's own terrain.sqlite is the starting point, so what it already shows stays.
  5 addresses  with --addresses: tools/build_addresses_osm.py -> <work>/out/addresses/<code>.sqlite, one per region
               house addresses from the raw extract, found as "Kaiserstraße 12, Buseck"
  6 install    with --data: the built files go to <data>/derived/geo/, what they replace moves to <work>/replaced-<time>/,
               the map's cached answers are cleared, and map-set.json is written so the app's own check of the
               library accepts the new map (engine/setup/install.py check_map).

The app must be closed while step 6 runs. Building heights for the 3D view are not built here.
The place finder is replaced, so US place names are no longer in it. Size: every region adds its whole street
network. A German state is a few hundred MB to a few GB as a built map; all of Europe at this detail is far
more than a phone-sized pack and has not been tried.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent))
GEOFABRIK = 'https://download.geofabrik.de/'


def geofabrik(spec):
    """'europe/france/alsace:Alsace' -> a region, as a region file would give it."""
    path, _, label = spec.partition(':')
    path = path.strip('/')
    if '//' in spec or not re.fullmatch(r'[a-z0-9-]+(/[a-z0-9-]+)*', path):     # a pasted URL is not a path
        sys.exit(f'--geofabrik takes a path such as europe/germany/hessen, not {spec!r}')
    slug = path.rsplit('/', 1)[-1]
    return {'code': slug, 'label': label or slug.replace('-', ' ').title(),
            'gpkg_url': f'{GEOFABRIK}{path}-latest-free.gpkg.zip', 'pbf_url': f'{GEOFABRIK}{path}-latest.osm.pbf',
            'source': f'OpenStreetMap contributors, via Geofabrik {slug}-latest-free.gpkg.zip (ODbL 1.0)'}


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


def terrain(out, data, work, workers, dem_base=None):
    """Elevation for the box of the street map just built, added to a copy of the data folder's terrain if it has one."""
    import sqlite3
    box = sqlite3.connect(out / 'map.sqlite').execute("SELECT value FROM meta WHERE key='bounds'").fetchone()
    if not box or not box[0]:
        sys.exit('the street map has no bounds, so there is no box to fetch elevation for')
    target = out / 'terrain.sqlite'
    have = data / 'derived' / 'geo' / 'terrain.sqlite' if data else None
    if not target.exists() and have and have.is_file():
        shutil.copy2(have, target)      # the pack's broad relief stays; this region's tiles are added to it
    run(TOOLS / 'fetch_copernicus_dem.py', '--bbox', box[0], '--out', work / 'dem', *(['--base', dem_base] if dem_base else []))
    run(TOOLS / 'build_terrain.py', '--src', work / 'dem', '--out', target, '--workers', workers, '--bbox', box[0],
        '--source-name', 'Copernicus DEM GLO-30 (© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA)')
    db = sqlite3.connect(target)
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    db.execute('PRAGMA journal_mode=DELETE')    # one file to copy, no -wal beside it
    db.close()


def install(out, data, work, code, built=('map.sqlite', 'places.sqlite')):
    from engine.setup import install as setup_install
    geo = data / 'derived' / 'geo'
    if not (data / 'library-data' / 'catalog.json').is_file():
        sys.exit(f'{data} is not a Lastbook data folder (no library-data/catalog.json)')
    geo.mkdir(parents=True, exist_ok=True)
    kept = work / time.strftime('replaced-%Y%m%d-%H%M%S')
    stale = [geo / n for n in (*built, 'socal-cells.json', 'tilecache')]
    stale += [geo / (n + side) for n in built for side in setup_install.SQLITE_SIDES]
    stale.append(data / 'map-set.json')
    for p in stale:
        if p.exists():
            kept.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(kept / p.name))
    for name in built:
        shutil.copy2(out / name, geo / name)
    for index in sorted((out / 'addresses').glob('*.sqlite')):      # beside the map, not part of the map set
        (geo / 'addresses').mkdir(exist_ok=True)
        shutil.copy2(index, geo / 'addresses' / index.name)
    files = {rel: (data / rel).stat().st_size for rel in setup_install.map_files(data) if rel != 'map-set.json'}
    (data / 'map-set.json').write_text(json.dumps({'name': code, 'files': files}, indent=1), encoding='utf-8')
    setup_install.check_map(data)
    print('installed in', geo, '· replaced files kept in', kept if kept.exists() else '(nothing was replaced)', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('regions', nargs='*', help='region files such as tools/regions/hessen.json')
    ap.add_argument('--geofabrik', action='append', default=[], metavar='PATH[:LABEL]',
                    help='a region by its path on download.geofabrik.de, such as europe/france/alsace:Alsace; may be repeated')
    ap.add_argument('--work', required=True, help='folder for downloads and built files (several GB for a German state)')
    ap.add_argument('--data', help='Lastbook data folder to install into; without it the map is only built')
    ap.add_argument('--label', help='what the whole map is called when it has several regions (default: their labels, joined)')
    ap.add_argument('--gpkg', help='one region only: a Geofabrik "free" .gpkg or .gpkg.zip already on this computer')
    ap.add_argument('--pbf', help='one region only: its .osm.pbf (or .osm) already on this computer')
    ap.add_argument('--addresses', action='store_true', help='also build the house address search from the .osm.pbf')
    ap.add_argument('--terrain', action='store_true', help='also build relief and contour lines from Copernicus DEM GLO-30')
    ap.add_argument('--dem-base', help='another place to fetch the elevation cells from (see tools/fetch_copernicus_dem.py --base)')
    ap.add_argument('--workers', type=int, default=2, help='processes for --terrain, about 1 GB of memory each (default 2)')
    ap.add_argument('--no-boundaries', action='store_true', help='skip postal codes, municipalities and districts (no .osm.pbf, no osmium needed)')
    a = ap.parse_args()
    regions = [json.loads(Path(r).read_text(encoding='utf-8')) for r in a.regions] + [geofabrik(g) for g in a.geofabrik]
    if not regions:
        ap.error('name at least one region file or --geofabrik region')
    if (a.gpkg or a.pbf) and len(regions) != 1:
        ap.error('--gpkg and --pbf are for a single region')
    if not a.no_boundaries or a.addresses:
        try:
            import osmium  # noqa: F401
        except ImportError:
            sys.exit('Postal codes and boundaries need the osmium package (pip install osmium), or pass --no-boundaries.')
    work = Path(a.work).expanduser().resolve()
    out = work / 'out'
    out.mkdir(parents=True, exist_ok=True)
    label = a.label or ', '.join(r['label'] for r in regions)
    code = '+'.join(r['code'] for r in regions) if len(regions) <= 4 else f"{regions[0]['code']}+{len(regions) - 1}"

    # Everything is downloaded before anything is built: a missing file should stop the run before hours of work, not after
    got = []
    for r in regions:
        gpkg = Path(a.gpkg).expanduser() if a.gpkg else fetch(r['gpkg_url'], work / r['gpkg_url'].rsplit('/', 1)[1])
        pbf = None
        if not a.no_boundaries or a.addresses:
            pbf = Path(a.pbf).expanduser() if a.pbf else fetch(r['pbf_url'], work / r['pbf_url'].rsplit('/', 1)[1])
        got.append((r, gpkg, pbf))

    places = [TOOLS / 'build_places_osm.py', '--map', out / 'map.sqlite', '--out', out / 'places.sqlite', '--label', label,
              '--levels', regions[0].get('admin_levels', '6,8')]
    for i, (r, gpkg, pbf) in enumerate(got):
        as_of = time.strftime('%Y-%m-%d', time.gmtime(gpkg.stat().st_mtime))
        print('streets:', r['label'], flush=True)
        run(TOOLS / 'build_map.py', gpkg_from(gpkg, work), out / 'map.sqlite', '--source', r['source'], '--as-of', as_of, *(['--append'] if i else []))
        if pbf and not a.no_boundaries:
            places += ['--pbf', f"{pbf}={r['label']}"]
    run(*places)
    if a.addresses:
        for r, _, pbf in got:
            print('addresses:', r['label'], flush=True)
            run(TOOLS / 'build_addresses_osm.py', pbf, out / 'addresses' / f"{r['code']}.sqlite", '--code', r['code'])
    data = Path(a.data).expanduser().resolve() if a.data else None
    built = ['map.sqlite', 'places.sqlite']
    if a.terrain:
        terrain(out, data, work, a.workers, a.dem_base)
        built.append('terrain.sqlite')
    for name in built:
        print(name, f'{(out / name).stat().st_size / 1e6:.1f} MB', flush=True)
    if data:
        install(out, data, work, code, built)


if __name__ == '__main__':
    main()
