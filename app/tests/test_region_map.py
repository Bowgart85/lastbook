"""A region outside the US: tools/build_map.py with --source, and tools/build_places_osm.py.

  python3 -B -m unittest app.tests.test_region_map

Builds a few features around Buseck (Hessen) as a tiny Geofabrik-style GeoPackage and a tiny .osm file, runs the
two tools as their own processes, and reads what they wrote. The postal code and boundary part needs the osmium
package and is skipped without it.
"""
import importlib.util
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = {'gis_osm_water_a_free': 'fclass,name', 'gis_osm_natural_a_free': 'fclass,name', 'gis_osm_landuse_a_free': 'fclass,name',
          'gis_osm_protected_areas_a_free': 'fclass', 'gis_osm_waterways_free': 'fclass,name', 'gis_osm_railways_free': 'fclass,name',
          'gis_osm_roads_free': 'fclass,name,ref', 'gis_osm_buildings_a_free': 'fclass,name', 'gis_osm_places_free': 'fclass,population,name',
          'gis_osm_pois_free': 'fclass,name', 'gis_osm_pois_a_free': 'fclass,name', 'gis_osm_natural_free': 'fclass,name'}


def gp(wkb):
    return b'GP\x00\x01' + struct.pack('<i', 4326) + wkb     # GeoPackage header: little-endian, no envelope


def point(lon, lat):
    return gp(struct.pack('<BIdd', 1, 1, lon, lat))


def line(*pts):
    return gp(struct.pack('<BII', 1, 2, len(pts)) + b''.join(struct.pack('<dd', *p) for p in pts))


def make_second_gpkg(path):
    """A neighbouring region: one road and one town near Aschaffenburg (Bayern)."""
    db = sqlite3.connect(path)
    for table, cols in TABLES.items():
        db.execute(f'CREATE TABLE {table}(geom BLOB,{cols})')
    db.execute("INSERT INTO gis_osm_roads_free VALUES (?,?,?,?)", (line((9.10, 49.97), (9.16, 49.98)), 'primary', 'Würzburger Straße', None))
    db.execute("INSERT INTO gis_osm_places_free VALUES (?,?,?,?)", (point(9.15, 49.975), 'town', 70000, 'Aschaffenburg'))
    db.execute("INSERT INTO gis_osm_pois_free VALUES (?,?,?)", (point(9.14, 49.97), 'pharmacy', 'Stadt-Apotheke'))
    db.commit()
    db.close()


SECOND_OSM = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="1" version="1" lat="49.95" lon="9.10"/><node id="2" version="1" lat="49.95" lon="9.20"/>
 <node id="3" version="1" lat="50.00" lon="9.20"/><node id="4" version="1" lat="50.00" lon="9.10"/>
 <way id="10" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
 <relation id="100" version="1"><member type="way" ref="10" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="postal_code"/><tag k="postal_code" v="63739"/><tag k="note" v="63739 Aschaffenburg"/></relation>
</osm>
'''


def make_gpkg(path):
    db = sqlite3.connect(path)
    for table, cols in TABLES.items():
        db.execute(f'CREATE TABLE {table}(geom BLOB,{cols})')
    db.execute("INSERT INTO gis_osm_roads_free VALUES (?,?,?,?)", (line((8.78, 50.60), (8.80, 50.61)), 'residential', 'Kaiserstraße', None))
    db.execute("INSERT INTO gis_osm_roads_free VALUES (?,?,?,?)", (line((8.70, 50.58), (8.90, 50.62)), 'motorway', None, 'A 5'))
    db.execute("INSERT INTO gis_osm_places_free VALUES (?,?,?,?)", (point(8.7833, 50.6), 'village', 6000, 'Großen-Buseck'))
    db.execute("INSERT INTO gis_osm_places_free VALUES (?,?,?,?)", (point(8.6784, 50.5841), 'city', 90000, 'Gießen'))
    db.execute("INSERT INTO gis_osm_pois_free VALUES (?,?,?)", (point(8.69, 50.57), 'hospital', 'Universitätsklinikum'))
    db.execute("INSERT INTO gis_osm_pois_free VALUES (?,?,?)", (point(8.70, 50.58), 'restaurant', 'Not a help point'))
    db.commit()
    db.close()


OSM_FILE = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="1" version="1" lat="50.58" lon="8.74"/><node id="2" version="1" lat="50.58" lon="8.84"/>
 <node id="3" version="1" lat="50.64" lon="8.84"/><node id="4" version="1" lat="50.64" lon="8.74"/>
 <way id="10" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
 <relation id="100" version="1"><member type="way" ref="10" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="postal_code"/><tag k="postal_code" v="35418"/><tag k="note" v="35418 Buseck"/></relation>
 <relation id="101" version="1"><member type="way" ref="10" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="8"/><tag k="name" v="Buseck"/></relation>
 <relation id="102" version="1"><member type="way" ref="10" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="6"/><tag k="name" v="Landkreis Gießen"/></relation>
 <relation id="103" version="1"><member type="way" ref="10" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="4"/><tag k="name" v="Hessen"/></relation>
</osm>
'''


def run(*args):
    return subprocess.run([sys.executable, '-B', *map(str, args)], capture_output=True, text=True, cwd=ROOT)


class RegionMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.opened = []
        make_gpkg(cls.dir / 'region.gpkg')
        cls.map = cls.dir / 'map.sqlite'
        cls.built = run(ROOT / 'tools/build_map.py', cls.dir / 'region.gpkg', cls.map, '--source', 'OpenStreetMap, test extract', '--as-of', '2026-11-01')

    @classmethod
    def tearDownClass(cls):
        for con in cls.opened:      # Windows does not delete a file that is still open
            con.close()
        cls.tmp.cleanup()

    @classmethod
    def db(cls, path):
        con = sqlite3.connect(path)
        cls.opened.append(con)
        return con

    def places(self, *extra):
        out = self.dir / f'places-{len(extra)}.sqlite'
        r = run(ROOT / 'tools/build_places_osm.py', '--map', self.map, '--out', out, '--label', 'Hessen', *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.db(out)

    def find(self, db, q):
        return db.execute('SELECT p.name,p.kind,p.detail,p.lat,p.lon FROM place_fts f JOIN place p ON p.id=f.rowid WHERE place_fts MATCH ? ORDER BY p.rank',
                          (f'"{q}"*',)).fetchall()

    def test_map_holds_the_region(self):
        self.assertEqual(self.built.returncode, 0, self.built.stderr)
        db = self.db(self.map)
        meta = dict(db.execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['source'], 'OpenStreetMap, test extract')
        self.assertEqual(meta['data_as_of'], '2026-11-01')
        self.assertEqual(meta['bounds'], '8.68,50.58,8.90,50.62')      # measured from the features, not Southern California's
        self.assertEqual(db.execute("SELECT name FROM feat WHERE layer='road' ORDER BY name").fetchall(), [('A 5',), ('Kaiserstraße',)])
        self.assertEqual(db.execute('SELECT cls,name FROM poi').fetchall(), [('hospital', 'Universitätsklinikum')])

    def test_without_options_the_map_is_described_as_before(self):
        out = self.dir / 'plain.sqlite'
        self.assertEqual(run(ROOT / 'tools/build_map.py', self.dir / 'region.gpkg', out).returncode, 0)
        meta = dict(self.db(out).execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['bounds'], '-121.36,32.50,-114.10,35.89')
        self.assertIn('socal', meta['source'])

    def test_a_county_named_twice_is_labelled_once(self):
        """Hessen's extract holds Werra-Meißner-Kreis as two county points; the map names it once."""
        src, out = self.dir / 'twice.gpkg', self.dir / 'twice.sqlite'
        make_gpkg(src)
        db = sqlite3.connect(src)
        for lon, lat, name in ((9.933, 51.180, 'Werra-Meißner-Kreis'), (9.925, 51.249, 'Werra-Meißner-Kreis'), (9.25, 50.60, 'Vogelsbergkreis')):
            db.execute("INSERT INTO gis_osm_places_free VALUES (?,?,?,?)", (point(lon, lat), 'county', None, name))
        db.execute("INSERT INTO gis_osm_places_free VALUES (?,?,?,?)", (point(8.80, 50.61), 'village', 500, 'Großen-Buseck'))   # two villages may share a name
        db.commit()
        db.close()
        r = run(ROOT / 'tools/build_map.py', src, out, '--source', 'test', '--as-of', '2026-11-17')
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.db(out)
        self.assertEqual([n for (n,) in got.execute("SELECT name FROM feat WHERE layer='place' AND cls='county' ORDER BY name")],
                         ['Vogelsbergkreis', 'Werra-Meißner-Kreis'])
        self.assertEqual(got.execute("SELECT COUNT(*) FROM feat WHERE layer='place' AND name='Großen-Buseck'").fetchone()[0], 2)

    def test_an_unknown_option_is_refused(self):
        self.assertNotEqual(run(ROOT / 'tools/build_map.py', self.dir / 'region.gpkg', self.dir / 'no.sqlite', '--bound', '1,2,3,4').returncode, 0)

    def test_places_from_the_street_map(self):
        db = self.places()
        hit = self.find(db, 'Großen-Buseck')
        self.assertEqual([(h[0], h[1], h[2]) for h in hit], [('Großen-Buseck', 'village', 'Hessen (OpenStreetMap) · Grossen-Buseck')])
        self.assertAlmostEqual(hit[0][3], 50.6, places=4)
        self.assertAlmostEqual(hit[0][4], 8.7833, places=4)
        self.assertEqual([h[0] for h in self.find(db, 'Giessen')], ['Gießen'])   # ß typed as ss
        self.assertEqual([h[0] for h in self.find(db, 'Gießen')], ['Gießen'])
        self.assertEqual(len(self.find(db, 'Universitatsklinikum')), 1)  # ä is matched by a
        self.assertEqual(dict(db.execute('SELECT key,value FROM meta'))['label'], 'Hessen')

    @unittest.skipUnless(importlib.util.find_spec('osmium'), 'needs the osmium package')
    def test_postal_codes_and_boundaries(self):
        osm = self.dir / 'region.osm'
        osm.write_text(OSM_FILE, encoding='utf-8')
        db = self.places('--pbf', osm)
        plz = self.find(db, '35418')
        self.assertEqual([(p[0], p[1], p[2]) for p in plz], [('35418', 'postal code', 'Buseck, Hessen')])
        self.assertAlmostEqual(plz[0][3], 50.61, places=3)             # centre of the square
        self.assertAlmostEqual(plz[0][4], 8.79, places=3)
        kinds = {(n, k) for n, k, *_ in self.find(db, 'Buseck')}
        self.assertIn(('Buseck', 'municipality'), kinds)
        self.assertEqual([(n, k) for n, k, *_ in self.find(db, 'Landkreis')], [('Landkreis Gießen', 'district')])
        self.assertEqual([n for n, *_ in self.find(db, 'Giessen') if n.startswith('Landkreis')], ['Landkreis Gießen'])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM place WHERE name='Hessen'").fetchone()[0], 0)   # admin_level 4 is not asked for

    def test_a_second_region_is_added_to_the_map(self):
        out = self.dir / 'two.sqlite'
        make_second_gpkg(self.dir / 'second.gpkg')
        self.assertEqual(run(ROOT / 'tools/build_map.py', self.dir / 'region.gpkg', out, '--source', 'first', '--as-of', '2026-11-02').returncode, 0)
        r = run(ROOT / 'tools/build_map.py', self.dir / 'second.gpkg', out, '--source', 'second', '--as-of', '2026-10-30', '--append')
        self.assertEqual(r.returncode, 0, r.stderr)
        db = self.db(out)
        self.assertEqual([n for (n,) in db.execute("SELECT name FROM feat WHERE layer='road' ORDER BY id")], ['Kaiserstraße', 'A 5', 'Würzburger Straße'])
        self.assertEqual(db.execute('SELECT COUNT(*),COUNT(DISTINCT id) FROM feat_idx').fetchone(), (6, 6))    # 2 roads and 2 places, then 1 and 1
        self.assertEqual([n for (n,) in db.execute('SELECT name FROM poi ORDER BY id')], ['Universitätsklinikum', 'Stadt-Apotheke'])
        meta = dict(db.execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['source'], 'first; second')
        self.assertEqual(meta['data_as_of'], '2026-10-30')             # the older of the two
        self.assertEqual(meta['bounds'], '8.68,49.97,9.16,50.62')      # both regions

    @unittest.skipUnless(importlib.util.find_spec('osmium'), 'needs the osmium package')
    def test_two_regions_from_download_to_data_folder(self):
        """tools/build_region.py with two region files whose downloads are files here: nothing leaves this computer."""
        import json
        import zipfile
        src, work, data = self.dir / 'src', self.dir / 'work', self.dir / 'LastbookData'
        src.mkdir()
        (data / 'library-data').mkdir(parents=True)
        (data / 'library-data/catalog.json').write_text('[]')
        (data / 'derived/geo').mkdir(parents=True)
        (data / 'derived/geo/places.sqlite').write_text('the place finder that was there')
        (data / 'derived/geo/terrain.sqlite').write_text('another map file, left alone')
        files = []
        for slug, code, label, gpkg, osm in (('hessen', 'HE', 'Hessen', make_gpkg, OSM_FILE), ('bayern', 'BY', 'Bayern', make_second_gpkg, SECOND_OSM)):
            gpkg(src / f'{slug}.gpkg')
            with zipfile.ZipFile(src / f'{slug}-latest-free.gpkg.zip', 'w') as z:
                z.write(src / f'{slug}.gpkg', f'{slug}.gpkg')
            (src / f'{slug}-latest.osm').write_text(osm, encoding='utf-8')
            f = src / f'{slug}.json'
            f.write_text(json.dumps({'code': code, 'label': label, 'gpkg_url': (src / f'{slug}-latest-free.gpkg.zip').as_uri(),
                                     'pbf_url': (src / f'{slug}-latest.osm').as_uri(), 'source': f'test {slug}'}), encoding='utf-8')
            files.append(f)
        r = run(ROOT / 'tools/build_region.py', *files, '--work', work, '--data', data)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        places = self.db(data / 'derived/geo/places.sqlite')
        self.assertEqual([(p[0], p[2]) for p in self.find(places, '35418')], [('35418', 'Buseck, Hessen')])
        self.assertEqual([(p[0], p[2]) for p in self.find(places, '63739')], [('63739', 'Aschaffenburg, Bayern')])
        self.assertEqual([p[2] for p in self.find(places, 'Aschaffenburg') if p[1] == 'town'], ['Hessen, Bayern (OpenStreetMap)'])
        roads = self.db(data / 'derived/geo/map.sqlite').execute("SELECT COUNT(*) FROM feat WHERE layer='road'").fetchone()[0]
        self.assertEqual(roads, 3)
        map_set = json.loads((data / 'map-set.json').read_text())
        self.assertEqual(map_set['name'], 'HE+BY')
        self.assertEqual(set(map_set['files']), {'derived/geo/map.sqlite', 'derived/geo/places.sqlite', 'derived/geo/terrain.sqlite'})
        kept = list(work.glob('replaced-*/places.sqlite'))
        self.assertEqual([k.read_text() for k in kept], ['the place finder that was there'])
        self.assertEqual((data / 'derived/geo/terrain.sqlite').read_text(), 'another map file, left alone')

    @unittest.skipUnless(importlib.util.find_spec('tifffile') and importlib.util.find_spec('numpy'), 'needs tifffile and numpy')
    def test_terrain_from_a_copernicus_cell(self):
        """One made-up 1° cell (south-west corner 50°N 8°E) whose height is a plane: fetched from a folder, built, read back."""
        import math
        import zlib
        import numpy as np
        import tifffile
        bucket, dem, out = self.dir / 'bucket', self.dir / 'dem', self.dir / 'terrain.sqlite'
        name = 'Copernicus_DSM_COG_10_N50_00_E008_00_DEM'
        (bucket / name).mkdir(parents=True)
        rows, cols = 3600, 2400                                   # 1 arc-second by 1.5: the real grid at this latitude
        lat = 51 - (np.arange(rows) + 0.5) / rows
        lon = 8 + (np.arange(cols) + 0.5) / cols
        height = (200 + 300 * (lat[:, None] - 50) + 100 * (lon[None, :] - 8)).astype(np.float32)
        tifffile.imwrite(bucket / name / f'{name}.tif', height, extratags=[
            (33550, 'd', 3, (1 / cols, 1 / rows, 0.0), False), (33922, 'd', 6, (0.0, 0.0, 0.0, 8.0, 51.0, 0.0), False)])
        r = run(ROOT / 'tools/fetch_copernicus_dem.py', '--bbox', '8.7,50.5,9.4,50.7', '--out', dem, '--base', bucket.as_uri() + '/')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('1 cells', r.stdout)                         # 8-9°E is there; 9-10°E is "sea"
        r = run(ROOT / 'tools/build_terrain.py', '--src', dem, '--out', out, '--workers', '1', '--source-name', 'Copernicus DEM GLO-30')
        self.assertEqual(r.returncode, 0, r.stderr)
        db = self.db(out)
        self.assertEqual(dict(db.execute('SELECT key,value FROM meta'))['source'], 'Copernicus DEM GLO-30')
        self.assertEqual([z for (z,) in db.execute('SELECT DISTINCT z FROM tile ORDER BY z')], list(range(4, 13)))
        want_lat, want_lon, z = 50.6, 8.7833, 12                   # Großen-Buseck
        n = 2 ** z
        fx = (want_lon + 180) / 360 * n
        fy = (1 - math.asinh(math.tan(math.radians(want_lat))) / math.pi) / 2 * n
        png = db.execute('SELECT png FROM tile WHERE z=? AND x=? AND y=?', (z, int(fx), int(fy))).fetchone()[0]
        i = png.index(b'IDAT')
        size = int.from_bytes(png[i - 4:i], 'big')
        raw = np.frombuffer(zlib.decompress(png[i + 4:i + 4 + size]), np.uint8).reshape(256, 1 + 256 * 3)
        self.assertTrue((raw[:, 0] == 2).all())                    # every row filtered "Up"
        rgb = np.cumsum(raw[:, 1:].astype(np.uint32), axis=0).astype(np.uint8).reshape(256, 256, 3).astype(np.uint32)
        px = rgb[int((fy % 1) * 256), int((fx % 1) * 256)]
        metres = -10000 + (int(px[0]) * 65536 + int(px[1]) * 256 + int(px[2])) * 0.1
        self.assertAlmostEqual(metres, 200 + 300 * 0.6 + 100 * 0.7833, delta=0.5)

    @unittest.skipUnless(importlib.util.find_spec('osmium'), 'needs the osmium package')
    def test_addresses_the_way_they_are_written_here(self):
        sys.path.insert(0, str(ROOT))
        from engine.address_search import find_addresses, fold, street_first
        self.assertEqual({fold(t) for t in ('Kaiserstraße', 'Kaiserstrasse', 'Kaiserstr.', 'KAISERSTR')}, {'kaiserstr'})
        self.assertEqual(fold('Straße der Républik'), 'str der republik')
        osm = self.dir / 'addr.osm'
        osm.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="1" version="1" lat="50.6000" lon="8.7800"><tag k="addr:housenumber" v="12a"/><tag k="addr:street" v="Kaiserstraße"/>
  <tag k="addr:city" v="Buseck"/><tag k="addr:postcode" v="35418"/></node>
 <node id="2" version="1" lat="50.5800" lon="8.6700"><tag k="addr:housenumber" v="12a"/><tag k="addr:street" v="Kaiserstraße"/>
  <tag k="addr:city" v="Gießen"/><tag k="addr:postcode" v="35390"/></node>
 <node id="3" version="1" lat="50.6100" lon="8.7900"><tag k="addr:housenumber" v="3;5"/><tag k="addr:street" v="Am Mühlberg"/></node>
 <node id="4" version="1" lat="50.6200" lon="8.7900"><tag k="addr:housenumber" v="7"/></node>
 <node id="5" version="1" lat="50.5805" lon="8.6705"><tag k="addr:housenumber" v="9"/><tag k="addr:street" v="Am Mühlberg"/></node>
 <node id="11" version="1" lat="50.6010" lon="8.7810"/><node id="12" version="1" lat="50.6010" lon="8.7830"/>
 <node id="13" version="1" lat="50.6030" lon="8.7830"/><node id="14" version="1" lat="50.6030" lon="8.7810"/>
 <node id="31" version="1" lat="50.59" lon="8.75"/><node id="32" version="1" lat="50.59" lon="8.85"/>
 <node id="33" version="1" lat="50.65" lon="8.85"/><node id="34" version="1" lat="50.65" lon="8.75"/>
 <node id="51" version="1" lat="50.55" lon="8.60"/><node id="52" version="1" lat="50.55" lon="8.72"/>
 <node id="53" version="1" lat="50.59" lon="8.72"/><node id="54" version="1" lat="50.59" lon="8.60"/>
 <way id="20" version="1"><nd ref="11"/><nd ref="12"/><nd ref="13"/><nd ref="14"/><nd ref="11"/>
  <tag k="building" v="yes"/><tag k="addr:housenumber" v="1"/><tag k="addr:street" v="Schloßgasse"/><tag k="addr:city" v="Buseck"/></way>
 <way id="40" version="1"><nd ref="31"/><nd ref="32"/><nd ref="33"/><nd ref="34"/><nd ref="31"/></way>
 <way id="60" version="1"><nd ref="51"/><nd ref="52"/><nd ref="53"/><nd ref="54"/><nd ref="51"/></way>
 <relation id="100" version="1"><member type="way" ref="40" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="postal_code"/><tag k="postal_code" v="35418"/></relation>
 <relation id="101" version="1"><member type="way" ref="40" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="8"/><tag k="name" v="Buseck"/></relation>
 <relation id="102" version="1"><member type="way" ref="60" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="6"/><tag k="name" v="Darmstadt"/></relation>
 <relation id="103" version="1"><member type="way" ref="60" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="admin_level" v="6"/><tag k="name" v="Landkreis Gießen"/></relation>
</osm>
''', encoding='utf-8')
        geo = self.dir / 'geo-addr'
        r = run(ROOT / 'tools/build_addresses_osm.py', osm, geo / 'addresses/HE.sqlite', '--code', 'HE')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('6 addresses', r.stdout)                     # 2 + the two of "3;5" + one more + the building; the node with no street is left out

        def found(q):
            return [(h['name'], h['detail']) for h in find_addresses(q, geo)]
        both = [('Kaiserstraße 12a', '35390 Gießen'), ('Kaiserstraße 12a', '35418 Buseck')]
        self.assertEqual(sorted(found('12a Kaiserstraße')), both)
        self.assertEqual(sorted(found('12A Kaiserstrasse')), both)
        self.assertEqual(sorted(found('12a Kaiserstr.')), both)
        self.assertEqual(found('12a Kaiserstraße Buseck'), [both[1]])
        self.assertEqual(found('12a Kaiserstr Giessen'), [both[0]])        # ß typed as ss, in the town too
        self.assertEqual(found('12a Kaiserstraße 35418'), [both[1]])
        self.assertEqual(found('13 Kaiserstraße'), [])                     # never a neighbouring house
        if importlib.util.find_spec('shapely'):
            self.assertIn('filled in from boundaries: 3 towns, 3 postal codes', r.stdout)
            # no town or postal code of its own: both come from the areas it lies in
            self.assertEqual(found('5 Am Muehlberg'), [('Am Mühlberg 5', '35418 Buseck')])
            self.assertEqual(found('5 Am Mühlberg Buseck'), [('Am Mühlberg 5', '35418 Buseck')])
            # no municipality there: the district that is a city of its own names it, the one called "Landkreis" does not
            self.assertEqual(found('9 Am Mühlberg'), [('Am Mühlberg 9', 'Darmstadt')])
            # what the mapper wrote stays: Gießen keeps its own town and code though it lies in that district's square
            self.assertEqual(found('12a Kaiserstr Giessen'), [both[0]])
        else:
            self.assertEqual(found('5 Am Muehlberg'), [('Am Mühlberg 5', '')])
        hit = find_addresses('1 Schlossgasse', geo)[0]
        self.assertEqual((hit['name'], hit['source']), ('Schloßgasse 1', 'OpenStreetMap'))
        self.assertAlmostEqual(hit['lat'], 50.602, places=4)               # the middle of the outline
        self.assertAlmostEqual(hit['lon'], 8.782, places=4)
        # the street-first way of writing it
        self.assertEqual(street_first('Kaiserstraße 12a, 35418 Buseck', geo), '12a Kaiserstraße Buseck 35418')
        self.assertEqual(street_first('Am Mühlberg 5', geo), '5 Am Mühlberg')
        self.assertEqual(found(street_first('Kaiserstr. 12 a Buseck', geo)), [both[1]])
        self.assertIsNone(street_first('35418', geo))
        self.assertIsNone(street_first('Buseck', geo))
        self.assertIsNone(street_first('Highway 101', self.dir))           # no street-first index there: stays a place search

    @unittest.skipUnless(importlib.util.find_spec('osmium'), 'needs the osmium package')
    def test_overview_fills_in_around_the_region_only(self):
        """Main roads and towns of a wider extract are added, except where the region map already has streets."""
        import shutil
        target = self.dir / 'with-overview.sqlite'
        shutil.copy2(self.map, target)                              # Hessen test map: a residential street at 8.78-8.80, 50.60
        osm = self.dir / 'wide.osm'
        osm.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="1" version="1" lat="50.60" lon="8.781"/><node id="2" version="1" lat="50.61" lon="8.790"/>
 <node id="3" version="1" lat="50.10" lon="8.60"/><node id="4" version="1" lat="50.05" lon="8.62"/><node id="5" version="1" lat="50.00" lon="8.65"/>
 <node id="6" version="1" lat="52.52" lon="13.40"><tag k="place" v="city"/><tag k="name" v="Berlin"/><tag k="population" v="3700000"/></node>
 <node id="7" version="1" lat="49.87" lon="8.65"><tag k="place" v="city"/><tag k="name" v="Darmstadt"/><tag k="population" v="160000"/></node>
 <node id="8" version="1" lat="50.605" lon="8.785"><tag k="place" v="town"/><tag k="name" v="Just across the edge"/></node>
 <node id="13" version="1" lat="50.59" lon="8.69"><tag k="place" v="city"/><tag k="name" v="Gießen"/></node>
 <node id="9" version="1" lat="49.50" lon="8.50"><tag k="place" v="village"/><tag k="name" v="Too small"/></node>
 <way id="10" version="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/><tag k="name" v="Already drawn in detail"/></way>
 <way id="11" version="1"><nd ref="3"/><nd ref="4"/><nd ref="5"/><tag k="highway" v="motorway"/><tag k="ref" v="A 5"/><tag k="name" v="Bundesautobahn 5"/></way>
 <way id="12" version="1"><nd ref="3"/><nd ref="5"/><tag k="highway" v="residential"/><tag k="name" v="Not a main road"/></way>
</osm>
''', encoding='utf-8')
        before = self.db(target).execute('SELECT COUNT(*) FROM feat').fetchone()[0]
        for _ in range(2):                                          # the second run replaces the first, it does not double it
            r = run(ROOT / 'tools/build_overview_osm.py', osm, target)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('1 main roads, 3 cities and towns added; 2 left out', r.stdout)   # left out: the street drawn in detail, and Gießen, which the map names
        db = self.db(target)
        added = db.execute('SELECT f.layer,f.cls,f.name,f.minz FROM feat f WHERE f.id > ? ORDER BY f.id', (before,)).fetchall()
        # a town in a cell that has the region's streets, but which the region map does not name, is added (Mainz beside Wiesbaden)
        self.assertEqual(added, [('place', 'city', 'Berlin', 5), ('place', 'city', 'Darmstadt', 6), ('place', 'town', 'Just across the edge', 9),
                                 ('road', 'motorway', 'A 5', 5)])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM feat').fetchone()[0], before + 4)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM feat_idx').fetchone()[0], before + 4)
        box = db.execute("SELECT i.minx,i.maxx,i.miny,i.maxy FROM feat_idx i JOIN feat f ON f.id=i.id WHERE f.name='A 5' AND f.cls='motorway' AND i.miny < 50.2").fetchone()
        self.assertEqual([round(v, 2) for v in box], [8.6, 8.65, 50.0, 50.1])

    @unittest.skipUnless(importlib.util.find_spec('osmium'), 'needs the osmium package')
    def test_a_country_extract_is_cut_down_to_the_overview(self):
        """tools/filter_overview_osm.py keeps main roads with their points, cities and towns, and nothing else."""
        import osmium
        import shutil
        wide, small = self.dir / 'country.osm', self.dir / 'country-overview.osm.pbf'
        wide.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="3" version="1" lat="50.10" lon="8.60"/><node id="4" version="1" lat="50.05" lon="8.62"/><node id="5" version="1" lat="50.00" lon="8.65"/>
 <node id="6" version="1" lat="52.52" lon="13.40"><tag k="place" v="city"/><tag k="name" v="Berlin"/><tag k="population" v="3700000"/></node>
 <node id="9" version="1" lat="49.50" lon="8.50"><tag k="place" v="village"/><tag k="name" v="Too small"/></node>
 <node id="20" version="1" lat="48.00" lon="9.00"><tag k="amenity" v="bench"/></node>
 <node id="21" version="1" lat="48.10" lon="9.10"/><node id="22" version="1" lat="48.20" lon="9.20"/>
 <way id="11" version="1"><nd ref="3"/><nd ref="4"/><nd ref="5"/><tag k="highway" v="motorway"/><tag k="ref" v="A 5"/></way>
 <way id="12" version="1"><nd ref="21"/><nd ref="22"/><tag k="highway" v="residential"/><tag k="name" v="Not a main road"/></way>
</osm>
''', encoding='utf-8')
        r = run(ROOT / 'tools/filter_overview_osm.py', wide, small)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('kept 1 main roads and 1 cities and towns', r.stdout)
        nodes, ways = set(), {}
        for obj in osmium.FileProcessor(str(small)).with_locations():
            if obj.is_node():
                nodes.add(obj.id)
            elif obj.is_way():
                ways[obj.id] = [n.location.valid() for n in obj.nodes]
        self.assertEqual(nodes, {3, 4, 5, 6})                       # the motorway's points and the city; no village, bench or side street
        self.assertEqual(ways, {11: [True, True, True]})
        self.assertNotEqual(run(ROOT / 'tools/filter_overview_osm.py', wide, wide).returncode, 0)     # never onto the extract itself
        target = self.dir / 'with-filtered-overview.sqlite'
        shutil.copy2(self.map, target)
        r = run(ROOT / 'tools/build_overview_osm.py', small, target)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('1 main roads, 1 cities and towns added', r.stdout)

    def test_a_geofabrik_path_names_its_downloads(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import build_region
        r = build_region.geofabrik('europe/france/alsace:Elsass')
        self.assertEqual((r['code'], r['label']), ('alsace', 'Elsass'))
        self.assertEqual(r['gpkg_url'], 'https://download.geofabrik.de/europe/france/alsace-latest-free.gpkg.zip')
        self.assertEqual(r['pbf_url'], 'https://download.geofabrik.de/europe/france/alsace-latest.osm.pbf')
        with self.assertRaises(SystemExit):
            build_region.geofabrik('https://example.org/x')

    def test_every_region_file_is_complete(self):
        import json
        files = sorted((ROOT / 'tools/regions').glob('*.json'))
        self.assertEqual(len(files), 16)
        for f in files:
            d = json.loads(f.read_text(encoding='utf-8'))
            self.assertTrue({'code', 'label', 'gpkg_url', 'pbf_url', 'source'} <= set(d), f.name)
            self.assertIn(f.stem + '-latest', d['gpkg_url'])
        self.assertEqual(len({json.loads(f.read_text(encoding='utf-8'))['code'] for f in files}), 16)


if __name__ == '__main__':
    unittest.main()
