#!/usr/bin/env python3
"""Street addresses for address search in a region outside the US, from OpenStreetMap.

  python3 tools/build_addresses_osm.py hessen-latest.osm.pbf derived/geo/addresses/HE.sqlite --code HE

tools/build_addresses.py does this for the US from Overture Maps. This writes the same addr table, so
engine/address_search.py reads either, with two differences it is told about in the meta table:
  layout = "street number"   results read "Kaiserstraße 12", and "Kaiserstraße 12, Buseck" can be typed
  norm is engine.address_search.fold(street)   so Kaiserstraße, Kaiserstrasse and Kaiserstr. all find it

Every node and every way (a building outline, filed at the middle of its nodes) with addr:housenumber and
addr:street or addr:place becomes a row. City and postal code are the object's own addr:city and addr:postcode.
Where a mapper left one out, it is taken from the area the address lies in: the postal code area
(boundary=postal_code) and the municipality (boundary=administrative at --levels' second number, 8 in Germany;
where there is none, as in a city that is its own district, the district, unless its name says "kreis").
That step needs the shapely package (2.0 or later) and is skipped with a note without it: such an address is
then found by street and number but not by town.
"3;5" and "3,5" are filed as two houses; "3-5" as written. Needs the osmium package. The extract is only read.
"""
import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.address_search import fold  # noqa: E402  (one rule for what is stored and what is typed)


def rows_of(tags, lat, lon, code):
    number, street = tags.get('addr:housenumber'), tags.get('addr:street') or tags.get('addr:place')
    if not number or not street:
        return
    street = ' '.join(street.split())
    norm = fold(street)
    if not norm:
        return
    city, postcode = ' '.join((tags.get('addr:city') or '').split()), (tags.get('addr:postcode') or '').strip()
    for n in re.split(r'[;,]', number):
        n = n.replace(' ', '')
        if n and len(n) <= 12:
            yield n, street, norm, city, code, postcode, round(lat, 6), round(lon, 6)


def fill_from_areas(db, pbf, district_level, municipality_level):
    """City and postal code for the rows that lack one, from the boundary each lies in. Returns (cities, codes) filled, or None."""
    try:
        import numpy as np
        import osmium
        import shapely
    except ImportError:
        return None
    if not hasattr(osmium, 'FileProcessor') or not hasattr(shapely, 'STRtree') or not hasattr(shapely, 'points'):
        return None
    todo = db.execute("SELECT rowid, lat, lon, city, zip FROM addr WHERE city='' OR zip=''").fetchall()
    if not todo:
        return 0, 0
    wkb = osmium.geom.WKBFactory()
    key = osmium.filter.KeyFilter('boundary')
    shapes, labels = [], []         # labels: ('zip', '35418') | ('city', 'Buseck') | ('district', 'Kassel')
    for obj in osmium.FileProcessor(str(pbf)).with_areas(key).with_filter(key):
        if not obj.is_area():
            continue
        tags = obj.tags
        boundary, level = tags.get('boundary'), tags.get('admin_level')
        if boundary == 'postal_code' and tags.get('postal_code'):
            label = ('zip', tags['postal_code'].strip())
        elif boundary == 'administrative' and tags.get('name') and level == str(municipality_level):
            label = ('city', tags['name'])
        elif boundary == 'administrative' and tags.get('name') and level == str(district_level) and 'kreis' not in tags['name'].lower():
            label = ('district', tags['name'])
        else:
            continue
        try:
            made = wkb.create_multipolygon(obj)
            shape = shapely.from_wkb(bytes.fromhex(made) if isinstance(made, str) else made)
        except Exception:           # a boundary that does not close: osmium cannot make an area of it
            continue
        if shape is not None and not shape.is_empty:
            shapes.append(shape)
            labels.append(label)
    if not shapes:
        return 0, 0
    tree = shapely.STRtree(shapes)
    cities = codes = 0
    for start in range(0, len(todo), 200_000):
        part = todo[start:start + 200_000]
        points = shapely.points(np.array([r[2] for r in part]), np.array([r[1] for r in part]))
        hits = {}
        for i, j in zip(*tree.query(points, predicate='within')):
            kind, value = labels[j]
            hits.setdefault(int(i), {}).setdefault(kind, value)
        updates = []
        for i, found in hits.items():
            rowid, _, _, city, code = part[i]
            new_city = city or found.get('city') or found.get('district') or ''
            new_code = code or found.get('zip') or ''
            if (new_city, new_code) != (city, code):
                cities += bool(new_city and not city)
                codes += bool(new_code and not code)
                updates.append((new_city, new_code, rowid))
        db.executemany('UPDATE addr SET city=?, zip=? WHERE rowid=?', updates)
    return cities, codes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pbf', help="the region's .osm.pbf (or .osm)")
    ap.add_argument('out', help='the index to write, such as derived/geo/addresses/HE.sqlite (replaced if it exists)')
    ap.add_argument('--code', required=True, help='short region code stored with each address, such as HE')
    ap.add_argument('--levels', default='6,8', help='admin_level of districts and of municipalities (default 6,8)')
    a = ap.parse_args()
    import osmium

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    t0, batch, total = time.time(), [], [0]

    def flush():
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
        total[0] += len(batch)
        batch.clear()

    def node(n):
        if 'addr:housenumber' in n.tags and n.location.valid():
            batch.extend(rows_of(n.tags, n.location.lat, n.location.lon, a.code))
            if len(batch) >= 100_000:
                flush()

    def way(w):
        if 'addr:housenumber' not in w.tags:
            return
        pts = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
        if pts:
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]      # a closed outline names its first corner twice
            batch.extend(rows_of(w.tags, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), a.code))

    if hasattr(osmium, 'FileProcessor') and hasattr(osmium, 'filter'):
        # Only objects with a house number reach Python; the rest of the extract is skipped inside the reader
        for obj in osmium.FileProcessor(str(a.pbf)).with_locations().with_filter(osmium.filter.KeyFilter('addr:housenumber')):
            if obj.is_node():
                node(obj)
            elif obj.is_way():
                way(obj)
    else:       # an older pyosmium: the same result, slowly
        class Addresses(osmium.SimpleHandler):
            def node(self, n):
                node(n)

            def way(self, w):
                way(w)

        Addresses().apply_file(str(a.pbf), locations=True, idx='flex_mem')
    flush()
    print(f'{total[0]:,} addresses, {time.time() - t0:.0f}s', flush=True)
    district, municipality = (int(v) for v in a.levels.split(','))
    filled = fill_from_areas(db, a.pbf, district, municipality)
    if filled is None:
        print('town and postal code not filled in from boundaries: that needs shapely 2 and numpy (pip install shapely numpy)', flush=True)
    else:
        print(f'filled in from boundaries: {filled[0]:,} towns, {filled[1]:,} postal codes, {time.time() - t0:.0f}s; indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('count', str(total[0])), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')), ('layout', 'street number'), ('credit', 'OpenStreetMap'),
        ('source', 'OpenStreetMap contributors (ODbL 1.0)')])
    db.commit()
    db.close()
    tmp.replace(out)
    print(f'done: {total[0]:,} addresses in {out}', flush=True)


if __name__ == '__main__':
    main()
