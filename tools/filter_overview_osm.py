#!/usr/bin/env python3
"""Cut a country extract down to what the overview needs: main roads and towns, with the roads' points.

  python3 tools/filter_overview_osm.py germany-latest.osm.pbf germany-overview.osm.pbf

tools/build_overview_osm.py wants a small file, because its reader keeps every node's position in memory.
This makes that file from a whole country (or Europe) with the osmium Python package alone; the osmium
command-line tool does the same with
  osmium tags-filter germany-latest.osm.pbf w/highway=motorway,trunk,primary n/place=city,town -o germany-overview.osm.pbf
and is not needed. What is kept is what build_overview_osm.py draws: its ROADS and PLACES.

The extract is read twice (once for the roads and towns, once for the points the roads refer to) and never
changed. An existing output file is replaced.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_overview_osm import PLACES, ROADS  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src', help='the extract of the wider area, such as germany-latest.osm.pbf')
    ap.add_argument('out', help='the filtered file to write, such as germany-overview.osm.pbf')
    a = ap.parse_args()
    import osmium

    src, out = Path(a.src).expanduser(), Path(a.out).expanduser()
    if not src.is_file():
        sys.exit(f'{src} is not there')
    if src.resolve() == out.resolve():
        sys.exit('the filtered file needs a name of its own: the extract is only read')
    t0 = time.time()
    wanted = osmium.filter.TagFilter(*[('highway', c) for c in ROADS], *[('place', c) for c in PLACES])
    roads = places = 0
    with osmium.BackReferenceWriter(str(out), ref_src=str(src), overwrite=True) as writer:
        for obj in osmium.FileProcessor(str(src), osmium.osm.NODE | osmium.osm.WAY).with_filter(wanted):
            if obj.is_way() and obj.tags.get('highway') in ROADS:
                writer.add(obj)
                roads += 1
            elif obj.is_node() and obj.tags.get('place') in PLACES:
                writer.add(obj)
                places += 1
    print(f'kept {roads:,} main roads and {places:,} cities and towns in {out.name}, {out.stat().st_size / 1e6:.1f} MB; {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
