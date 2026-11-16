#!/usr/bin/env python3
"""Fetch Copernicus DEM GLO-30 elevation cells (1 arc-second, about 30 m) for a box, for tools/build_terrain.py --src.

  python3 tools/fetch_copernicus_dem.py --bbox 7.7,49.3,10.3,51.7 --out ~/lastbook-work/dem

One GeoTIFF per 1° cell, from the public copy on Amazon S3 (the "copernicus-dem-30m" open-data bucket). A cell
that is all sea has no file there and is skipped. Files already in the folder are kept. Each is 10 to 40 MB.

Copernicus DEM is free to use with credit: "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018
provided under COPERNICUS by the European Union and ESA; all rights reserved". Check the current licence text
before passing a built map on.
"""
import argparse
import math
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'https://copernicus-dem-30m.s3.amazonaws.com/'


def cell_names(w, s, e, n):
    """The file stem of every 1° cell touching the box, named by its south-west corner."""
    for lat in range(math.floor(s), math.ceil(n)):
        for lon in range(math.floor(w), math.ceil(e)):
            yield 'Copernicus_DSM_COG_10_%s%02d_00_%s%03d_00_DEM' % ('N' if lat >= 0 else 'S', abs(lat), 'E' if lon >= 0 else 'W', abs(lon))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bbox', required=True, help='W,S,E,N in degrees')
    ap.add_argument('--out', required=True, help='folder for the GeoTIFFs')
    ap.add_argument('--base', default=BASE, help='where the cells are (default: the public S3 bucket)')
    a = ap.parse_args()
    w, s, e, n = map(float, a.bbox.split(','))
    if not (w < e and s < n):
        sys.exit('--bbox is W,S,E,N with W<E and S<N')
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    got = missing = 0
    for name in cell_names(w, s, e, n):
        dest = out / f'{name}.tif'
        if dest.exists():
            got += 1
            continue
        url = f'{a.base}{name}/{name}.tif'
        part = dest.with_name(dest.name + '.part')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'lastbook-fetch-dem'})
            with urllib.request.urlopen(req, timeout=120) as r, open(part, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
        except urllib.error.HTTPError as err:
            part.unlink(missing_ok=True)
            if err.code in (403, 404):      # no such cell: open sea
                missing += 1
                continue
            raise
        except (urllib.error.URLError, OSError) as err:
            part.unlink(missing_ok=True)
            if isinstance(getattr(err, 'reason', None), FileNotFoundError) or isinstance(err, FileNotFoundError):
                missing += 1                # a file: base used in tests
                continue
            raise
        part.replace(dest)
        got += 1
        print('got', dest.name, f'{dest.stat().st_size / 1e6:.0f} MB', flush=True)
    print(f'{got} cells in {out}, {missing} not offered (sea)', flush=True)
    if not got:
        sys.exit('no elevation cells for this box')


if __name__ == '__main__':
    main()
