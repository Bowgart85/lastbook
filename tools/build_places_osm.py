#!/usr/bin/env python3
"""Build the offline place finder (places.sqlite) for a region outside the US, from OpenStreetMap alone.

  python3 tools/build_places_osm.py --map derived/geo/map.sqlite --out derived/geo/places.sqlite --label Hessen
  python3 tools/build_places_osm.py ... --pbf hessen-latest.osm.pbf        # adds postal codes, municipalities, districts
  python3 tools/build_places_osm.py ... --label Deutschland --pbf hessen.osm.pbf=Hessen --pbf bayern.osm.pbf=Bayern

tools/build_places.py does this for the US from USGS and Census files. This one writes the same two tables
(place, place_fts), so the app reads either. What it finds:

  from the street map (--map, made by tools/build_map.py)
    named places (city, town, village, suburb...)                         rank 1
    named help points (hospital, pharmacy, drinking water...)             rank 4
  from the raw extract (--pbf, optional, needs the osmium package)
    postal code areas        boundary=postal_code + postal_code           rank 2   kind "postal code"
    municipalities           boundary=administrative, admin_level 8       rank 2   kind "municipality"
    districts                boundary=administrative, admin_level 6       rank 2   kind "district"

--pbf may be given once per extract; FILE=NAME files that extract's areas under NAME instead of --label.
The admin levels are Germany's (6 Kreis, 8 Gemeinde); --levels DISTRICT,MUNICIPALITY changes them.
An area is filed at the centroid of its largest outer ring. Both inputs are only read.
The search folds ä to a by itself but not ß to ss, so a name with ß carries its ss spelling beside it ("· Giessen").
"""
import argparse
import re
import sqlite3
import struct
from pathlib import Path

SCHEMA = '''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
  CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');
  CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);'''
INSERT = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
OSM = 'OpenStreetMap'


def centroid(ring):
    """Centroid of a closed ring of (lon, lat), with its absolute area. A ring with no area gives its mean point."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if abs(a) < 1e-12:
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring), 0.0
    return cx / (3 * a), cy / (3 * a), abs(a) / 2


def spelled(name, detail):
    """The detail, with the name's ss spelling after it when the name has an ß: typed without one, it is still found."""
    return f"{detail} · {name.replace('ß', 'ss')}" if 'ß' in name else detail


def from_map(db, path, label):
    src = sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True)
    detail = f'{label} ({OSM})'
    n = 0
    for cls, name, lon, lat in src.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
        db.execute(INSERT, (name, cls.replace('_', ' '), spelled(name, detail), lat, lon, 4, OSM))
        n += 1
    # Towns of an overview (tools/build_overview_osm.py) lie outside the region: that tool files them as "near" it
    was = src.execute("SELECT value FROM meta WHERE key='overview_ids'").fetchone()
    lo, hi = map(int, was[0].split('-')) if was else (0, -1)
    for cls, name, g in src.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL AND id NOT BETWEEN ? AND ?", (lo, hi)):
        _, _, x, y = struct.unpack_from('<iiii', g)     # one part, one point: see pack() in build_map.py
        db.execute(INSERT, (name, cls, spelled(name, detail), y / 1e6, x / 1e6, 1, OSM))
        n += 1
    src.close()
    return n


def from_pbf(db, path, label, district_level, municipality_level):
    import osmium       # only this step needs it

    wanted = {str(district_level): 'district', str(municipality_level): 'municipality'}
    found = []

    def area(a):
        tags = a.tags
        boundary = tags.get('boundary')
        if boundary == 'postal_code':
            code = (tags.get('postal_code') or '').strip()
            if not code:
                return
            # Germany's postal code relations carry note="35418 Buseck": the part after the code says where it is
            where = re.sub(r'^\s*%s\s*' % re.escape(code), '', tags.get('note') or '').strip()
            name, kind, detail = code, 'postal code', f'{where}, {label}' if where else label
        elif boundary == 'administrative' and tags.get('admin_level') in wanted and tags.get('name'):
            name, kind, detail = tags['name'], wanted[tags['admin_level']], label
        else:
            return
        best = None
        for outer in a.outer_rings():
            ring = [(n.lon, n.lat) for n in outer if n.location.valid()]
            if len(ring) >= 4:
                c = centroid(ring)
                if best is None or c[2] > best[2]:
                    best = c
        if best:
            found.append((name, kind, spelled(name, detail), best[1], best[0], 2, OSM))

    if hasattr(osmium, 'FileProcessor') and hasattr(osmium, 'filter'):
        # Only boundaries are put together as areas: without the filter every building and lake of the extract is too
        wanted_key = osmium.filter.KeyFilter('boundary')
        for obj in osmium.FileProcessor(str(path)).with_areas(wanted_key).with_filter(wanted_key):
            if obj.is_area():
                area(obj)
    else:       # an older pyosmium: the same result, slowly
        class Areas(osmium.SimpleHandler):
            def area(self, a):
                area(a)

        Areas().apply_file(str(path), locations=True, idx='flex_mem')
    # A municipality crossing the extract's edge, or one mapped twice, shows up more than once: keep one per name and spot
    seen = set()
    n = 0
    for row in sorted(found):
        key = (row[0], row[1], round(row[3], 2), round(row[4], 2))
        if key not in seen:
            seen.add(key)
            db.execute(INSERT, row)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--map', required=True, help='map.sqlite made by tools/build_map.py')
    ap.add_argument('--out', required=True, help='places.sqlite to write (replaced if it exists)')
    ap.add_argument('--label', required=True, help='what the region is called beside each result, such as Hessen')
    ap.add_argument('--pbf', action='append', default=[], metavar='FILE[=NAME]',
                    help='a region\'s .osm.pbf, for postal codes, municipalities and districts; may be repeated')
    ap.add_argument('--levels', default='6,8', help='admin_level of districts and of municipalities (default 6,8)')
    a = ap.parse_args()
    district, municipality = (int(v) for v in a.levels.split(','))
    out = Path(a.out)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)
    n = from_map(db, a.map, a.label)
    print('from the street map', n, flush=True)
    for item in a.pbf:
        path, _, name = item.partition('=') if '=' in Path(item).name else (item, '', '')
        m = from_pbf(db, path, name or a.label, district, municipality)
        print('postal codes, municipalities and districts', Path(path).name, m, flush=True)
        n += m
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    kinds = 'places and help points' + (', postal codes, municipalities and districts' if a.pbf else '')
    db.executemany('INSERT INTO meta VALUES (?,?)', [('label', a.label), ('source', f'{OSM} contributors (ODbL 1.0)'),
                                                     ('holds', f'{a.label}: {kinds} ({OSM})')])
    db.commit()
    db.close()
    print('places', n)


if __name__ == '__main__':
    main()
