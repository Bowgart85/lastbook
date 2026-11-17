#!/usr/bin/env python3
"""Add a wide-area overview (main roads and towns) around a region map, from OpenStreetMap.

  python3 tools/build_overview_osm.py germany-overview.osm.pbf derived/geo/map.sqlite

A region map made by tools/build_map.py ends at the region's edge; zoomed out, the land around it is empty.
This adds, for the area of a larger extract (a country, or Europe):
  motorways (from zoom 5), trunk roads (6), primary roads (8)   named by their ref ("A 5") where they have one
  cities (zoom 6; over 300,000 people: 5) and towns (9)
No road is added where the map already has street detail (0.05° cells that hold small features), and no city
or town the map already names within about 10 km, so the region itself is not drawn twice. A town just across
the region's edge is added: its cell has the region's streets, but the region map does not hold the town.
Run again, it first removes what it added before.

Give it a filtered extract, not a whole country: the reader keeps every node's position in memory.
tools/filter_overview_osm.py makes one with the osmium Python package:

  python3 tools/filter_overview_osm.py germany-latest.osm.pbf germany-overview.osm.pbf

Needs the osmium Python package. The extract is only read; the map is changed in place (close the app first).
"""
import argparse
import sqlite3
import sys
import time
from array import array
from pathlib import Path

Q = 1e6
CELL = 0.05
NEAR = 0.1          # degrees: a place of the same name this close in the region map is the same place
ROADS = {'motorway': (5, 0.0005), 'trunk': (6, 0.0005), 'primary': (8, 0.0003)}     # class: (first zoom, simplify tolerance in degrees)
PLACES = {'city': 6, 'town': 9}


def simplify(flat, tol):
    """As in tools/build_map.py: drop points closer than tol to the last kept one; the ends stay."""
    if len(flat) <= 4 or tol <= 0:
        return flat
    out = [flat[0], flat[1]]
    px, py = flat[0], flat[1]
    for i in range(2, len(flat) - 2, 2):
        x, y = flat[i], flat[i + 1]
        if abs(x - px) > tol or abs(y - py) > tol:
            out += [x, y]
            px, py = x, y
    return out + [flat[-2], flat[-1]]


def pack(parts):
    """As in tools/build_map.py: int32 nparts, then per part npts and quantized x,y deltas. The app reads this."""
    a = array('i', [len(parts)])
    for p in parts:
        n = len(p) // 2
        a.append(n)
        lx = ly = 0
        for i in range(n):
            x, y = int(round(p[2 * i] * Q)), int(round(p[2 * i + 1] * Q))
            a.append(x - lx)
            a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def cell(lon, lat):
    return int(lon // CELL), int(lat // CELL)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pbf', help='a filtered extract of the wider area (see above)')
    ap.add_argument('map', help='map.sqlite made by tools/build_map.py; changed in place')
    a = ap.parse_args()
    import osmium

    if not Path(a.map).is_file():
        sys.exit(f'{a.map} is not there: build the region map first')
    t0 = time.time()
    db = sqlite3.connect(a.map)
    was = db.execute("SELECT value FROM meta WHERE key='overview_ids'").fetchone()
    if was:     # an earlier run's features, before measuring where the detail is
        lo, hi = map(int, was[0].split('-'))
        db.execute('DELETE FROM feat WHERE id BETWEEN ? AND ?', (lo, hi))
        db.execute('DELETE FROM feat_idx WHERE id BETWEEN ? AND ?', (lo, hi))
    # Where the map has street detail: cells holding features that only show from zoom 13 (residential streets, tracks)
    detailed = set()
    for x0, x1, y0, y1 in db.execute('SELECT minx, maxx, miny, maxy FROM feat_idx WHERE minz >= 13 AND maxx - minx < 0.5 AND maxy - miny < 0.5'):
        (cx0, cy0), (cx1, cy1) = cell(x0, y0), cell(x1, y1)
        detailed.update((cx, cy) for cx in range(cx0, cx1 + 1) for cy in range(cy0, cy1 + 1))
    named = {}      # the places the region map names already, to tell a town it holds from one just beyond its edge
    for name, lon, lat in db.execute("SELECT f.name, i.minx, i.miny FROM feat f JOIN feat_idx i ON i.id=f.id WHERE f.layer='place' AND f.name IS NOT NULL"):
        named.setdefault(name, []).append((lon, lat))
    first = fid = db.execute('SELECT COALESCE(MAX(id),0) FROM feat').fetchone()[0] + 1
    roads = places = skipped = 0

    def add(layer, cls, name, minz, flat):
        nonlocal fid
        xs, ys = flat[0::2], flat[1::2]
        db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (fid, layer, cls, name, minz, pack([flat])))
        db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (fid, min(xs), max(xs), min(ys), max(ys), minz, 30))
        fid += 1

    wanted = osmium.filter.TagFilter(*[('highway', c) for c in ROADS], *[('place', c) for c in PLACES])
    for obj in osmium.FileProcessor(str(a.pbf)).with_locations().with_filter(wanted):
        tags = obj.tags
        if obj.is_way() and tags.get('highway') in ROADS:
            flat = [v for n in obj.nodes if n.location.valid() for v in (n.lon, n.lat)]
            if len(flat) < 4:
                continue
            mid = (len(flat) // 4) * 2
            if cell(flat[mid], flat[mid + 1]) in detailed:
                skipped += 1
                continue
            minz, tol = ROADS[tags['highway']]
            add('road', tags['highway'], tags.get('ref') or tags.get('name'), minz, simplify(flat, tol))
            roads += 1
        elif obj.is_node() and tags.get('place') in PLACES and tags.get('name') and obj.location.valid():
            lon, lat = obj.location.lon, obj.location.lat
            if any(abs(lon - x) < NEAR and abs(lat - y) < NEAR for x, y in named.get(tags['name'], ())):
                skipped += 1
                continue
            minz = PLACES[tags['place']]
            try:
                if int(tags.get('population') or 0) > 300000:
                    minz = 5
            except ValueError:
                pass
            add('place', tags['place'], tags['name'], minz, [obj.location.lon, obj.location.lat])
            places += 1
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('overview_ids', f'{first}-{fid - 1}'))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('overview', f'{roads} main roads and {places} towns from {Path(a.pbf).name} (OpenStreetMap, ODbL 1.0)'))
    db.commit()
    db.close()
    print(f'overview: {roads:,} main roads, {places:,} cities and towns added; {skipped:,} left out where the map has detail; {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
