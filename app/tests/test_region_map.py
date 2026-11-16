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
        make_gpkg(cls.dir / 'region.gpkg')
        cls.map = cls.dir / 'map.sqlite'
        cls.built = run(ROOT / 'tools/build_map.py', cls.dir / 'region.gpkg', cls.map, '--source', 'OpenStreetMap, test extract', '--as-of', '2026-11-01')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def places(self, *extra):
        out = self.dir / f'places-{len(extra)}.sqlite'
        r = run(ROOT / 'tools/build_places_osm.py', '--map', self.map, '--out', out, '--label', 'Hessen', *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return sqlite3.connect(out)

    def find(self, db, q):
        return db.execute('SELECT p.name,p.kind,p.detail,p.lat,p.lon FROM place_fts f JOIN place p ON p.id=f.rowid WHERE place_fts MATCH ? ORDER BY p.rank',
                          (f'"{q}"*',)).fetchall()

    def test_map_holds_the_region(self):
        self.assertEqual(self.built.returncode, 0, self.built.stderr)
        db = sqlite3.connect(self.map)
        meta = dict(db.execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['source'], 'OpenStreetMap, test extract')
        self.assertEqual(meta['data_as_of'], '2026-11-01')
        self.assertEqual(meta['bounds'], '8.68,50.58,8.90,50.62')      # measured from the features, not Southern California's
        self.assertEqual(db.execute("SELECT name FROM feat WHERE layer='road' ORDER BY name").fetchall(), [('A 5',), ('Kaiserstraße',)])
        self.assertEqual(db.execute('SELECT cls,name FROM poi').fetchall(), [('hospital', 'Universitätsklinikum')])

    def test_without_options_the_map_is_described_as_before(self):
        out = self.dir / 'plain.sqlite'
        self.assertEqual(run(ROOT / 'tools/build_map.py', self.dir / 'region.gpkg', out).returncode, 0)
        meta = dict(sqlite3.connect(out).execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['bounds'], '-121.36,32.50,-114.10,35.89')
        self.assertIn('socal', meta['source'])

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
        db = sqlite3.connect(out)
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
        places = sqlite3.connect(data / 'derived/geo/places.sqlite')
        self.assertEqual([(p[0], p[2]) for p in self.find(places, '35418')], [('35418', 'Buseck, Hessen')])
        self.assertEqual([(p[0], p[2]) for p in self.find(places, '63739')], [('63739', 'Aschaffenburg, Bayern')])
        self.assertEqual([p[2] for p in self.find(places, 'Aschaffenburg') if p[1] == 'town'], ['Hessen, Bayern (OpenStreetMap)'])
        roads = sqlite3.connect(data / 'derived/geo/map.sqlite').execute("SELECT COUNT(*) FROM feat WHERE layer='road'").fetchone()[0]
        self.assertEqual(roads, 3)
        map_set = json.loads((data / 'map-set.json').read_text())
        self.assertEqual(map_set['name'], 'HE+BY')
        self.assertEqual(set(map_set['files']), {'derived/geo/map.sqlite', 'derived/geo/places.sqlite', 'derived/geo/terrain.sqlite'})
        kept = list(work.glob('replaced-*/places.sqlite'))
        self.assertEqual([k.read_text() for k in kept], ['the place finder that was there'])
        self.assertEqual((data / 'derived/geo/terrain.sqlite').read_text(), 'another map file, left alone')

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
