#!/usr/bin/env python3
"""Street addresses for address search in a region outside the US, from OpenStreetMap.

  python3 tools/build_addresses_osm.py hessen-latest.osm.pbf derived/geo/addresses/HE.sqlite --code HE

tools/build_addresses.py does this for the US from Overture Maps. This writes the same addr table, so
engine/address_search.py reads either, with two differences it is told about in the meta table:
  layout = "street number"   results read "Kaiserstraße 12", and "Kaiserstraße 12, Buseck" can be typed
  norm is engine.address_search.fold(street)   so Kaiserstraße, Kaiserstrasse and Kaiserstr. all find it

Every node and every way (a building outline, filed at the middle of its nodes) with addr:housenumber and
addr:street or addr:place becomes a row. City and postal code are the object's own addr:city and addr:postcode;
where a mapper left them out they stay empty, and such an address is found by street and number but not by town.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pbf', help="the region's .osm.pbf (or .osm)")
    ap.add_argument('out', help='the index to write, such as derived/geo/addresses/HE.sqlite (replaced if it exists)')
    ap.add_argument('--code', required=True, help='short region code stored with each address, such as HE')
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

    class Addresses(osmium.SimpleHandler):
        def node(self, n):
            if 'addr:housenumber' in n.tags and n.location.valid():
                batch.extend(rows_of(n.tags, n.location.lat, n.location.lon, a.code))
                if len(batch) >= 100_000:
                    flush()

        def way(self, w):
            if 'addr:housenumber' not in w.tags:
                return
            pts = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
            if pts:
                if len(pts) > 1 and pts[0] == pts[-1]:
                    pts = pts[:-1]      # a closed outline names its first corner twice
                batch.extend(rows_of(w.tags, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), a.code))

    Addresses().apply_file(str(a.pbf), locations=True, idx='flex_mem')
    flush()
    print(f'{total[0]:,} addresses, {time.time() - t0:.0f}s; indexing', flush=True)
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
