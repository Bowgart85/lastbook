# Übergabe: Lastbook für Hessen/Deutschland + Heimserver

Übergabedokument für Claude Code. Stand: 2026-11-17. Basis: `Immortal-Protocols/lastbook`, Release 1.1.8, flacher Klon vom selben Tag.

## Stand (2026-11-17, Branch `hessen-port`)

Etappe 1 läuft mit echten Daten: Hessen-Karte am 17.11.2026 unter Windows 11 (Python 3.15.2) gebaut, in ein Small-Pack eingespielt und im Browser am PC und am iPhone geöffnet. Die Abnahmepunkte am Ende dieses Dokuments sind erfüllt bis auf Docker. Test bei getrenntem Internet bestanden (17.11.2026, Server ohne Docker am PC): Karte nutzbar, Videos der Bibliothek spielbar.

| Teil | Datei | Geprüft |
|---|---|---|
| Straßenkarte für beliebige Region | `tools/build_map.py` (neue Optionen `--source`, `--as-of`, `--bounds`; ohne Optionen unverändert); gleichnamige Kreis-Punkte nur einmal | Tests; ganz Hessen gebaut und im Browser angesehen |
| Ortssuche aus OSM: Orte, Hilfepunkte, PLZ, Gemeinden, Kreise; „Giessen" findet „Gießen" | `tools/build_places_osm.py` | Tests; mit echten Daten: „Buseck", „35418", „Giessen" |
| Ein Befehl: laden, bauen, einspielen, `map-set.json` schreiben; mehrere Regionen in einer Karte | `tools/build_region.py`, `tools/regions/*.json` (alle 16 Bundesländer), `--geofabrik` für jede andere Region | Tests; echter Download und Einspielen für Hessen |
| Metrische Anzeige außerhalb der USA (Maßstab, Höhen, Höhenlinien, Entfernungen, 3D) | `web/map.js`, `web/terrain3d.js` | im Browser: „1,9 km", „20 km", „410 m here"; 3D nicht angesehen |
| Kartendatum im Kopf aus `meta.data_as_of` statt fest „25 Oct 2026" | `web/map.js` | im Browser |
| Beschriftung: Städte vor Kreisen; deutlicheres Mittelpunktskreuz | `web/map.js` | im Browser |
| Kartenpanel nennt die Ortsdaten der Region | `server.py` (`pack_datasets`) | `/api/map/info` |
| Heimserver | `server.py --lan`; `packaging/docker/Dockerfile`, `compose.yaml`, `.dockerignore` | `--lan` unter Windows, iPhone im WLAN; **Docker-Image nicht gebaut** (Docker auf dem PC nicht installiert) |
| Gelände: Relief, Höhenlinien, Höhenangaben, 3D aus Copernicus DEM GLO-30 | `tools/fetch_copernicus_dem.py`, `tools/build_terrain.py` (`--src`, `--out`), `build_region.py --terrain` | Tests; 12 echte Kacheln geladen und gebaut, Relief und Höhe im Browser |
| Adresssuche: „Kaiserstraße 12, Buseck", auch als „Kaiserstr." oder „Kaiserstrasse" | `tools/build_addresses_osm.py`, `engine/address_search.py`, `server.py`, `build_region.py --addresses` | Tests; mit echten Daten: „Kaiserstr. 12, Buseck" |
| Übersicht um die Region herum (Fernstraßen, Städte) für weite Zoomstufen | `tools/filter_overview_osm.py` (Auszug filtern), `tools/build_overview_osm.py` (Orte jenseits der Kante bleiben; mit `--places` auch in der Ortssuche, als „near Hessen"), `build_region.py --overview DATEI` | Tests; Deutschland-Auszug gefiltert und eingespielt, Raum Mainz im Browser; Suche findet „Mainz", „Aschaffenburg", „Worms", „Würzburg" |
| Quellenangabe Copernicus auf der Karte, Kartenpanel nennt Höhenquelle und Übersicht | `server.py`, `web/map.js` | im Browser (Quellenzeile) und `/api/map/info` |
| Tests | `app/tests/test_region_map.py` (15 Tests) | grün unter Windows |

Bestehende Tests (Stand vor dem 17.11.2026, unter Linux): 319 gelaufen, 1 Fehler in `test_setup.Recommend.test_hardware_here`. Der Test erwartet macOS oder Windows und schlägt unter Linux auch ohne diese Änderungen fehl. Unter Windows nicht erneut gelaufen.

### Erster Lauf am PC (17.11.2026, Windows 11, Python 3.15.2)

| Schritt | Ergebnis |
|---|---|
| Geofabrik `hessen-latest-free.gpkg.zip`, `hessen-latest.osm.pbf` | Adressen in `tools/regions/hessen.json` stimmen; 597 MB und 348 MB |
| Small-Pack | `Lastbook-Small-20261113.zip`, 7,69 GB; Adresse und SHA-256 aus `https://downloads.lastbook.org/manifest-v1.json`; entpackt 840 Dateien |
| Straßenkarte | 4,6 Mio. Objekte, 46.448 Hilfepunkte, 76 bis 95 s; `map.sqlite` 858 MB |
| Ortssuche | 47.655 Orte, 6 MB |
| Adressen | 1.639.481 in 30 s, Ort und PLZ ergänzt in 42 s (38.192 Orte, 152.897 PLZ); `HE.sqlite` 172 MB |
| Gelände | 12 Copernicus-Kacheln, 3.504 Kacheln in 12 s; mit dem Relief des Packs 372 MB |
| Ganzer Lauf ohne Downloads | 138 bis 163 s |
| Übersicht Deutschland | `germany-latest.osm.pbf` 4,88 GB; gefiltert in 47 s auf 33,7 MB (349.312 Straßen, 2.320 Orte); eingespielt 314.933 Straßen, 2.142 Orte; `map.sqlite` danach 905 MB |
| Platz | `lastbook-work` rund 20 GB (Downloads einschließlich Pack-Zip und Deutschland-Auszug, Zwischendateien, ersetzte Dateien aus vier Läufen); `LastbookData` 8,5 GB |

Funde unter Windows:

- **Gelände:** `build_region.py` übernimmt das Relief des Packs nur, wenn `out/terrain.sqlite` noch nicht existiert. Wer zuerst ohne `--data` baut, muss die Datei vor dem Lauf mit `--data` wegschieben, sonst ersetzt die Region allein das Relief des Packs.
- **Firewall:** Beim ersten Start mit `--lan` fragt Windows nach. Wird nicht zugelassen, legt Windows Blockier-Regeln für Python an, und kein anderes Gerät kommt durch.
- **VPN:** Mit aktivem VPN druckt der Server den Telefon-Link mit der VPN-Adresse. Fürs Heimnetz die LAN-Adresse des PC nehmen.
- **Telefon-Link:** Nach dem ersten Aufruf mit `?key=` leitet der Server auf `/` um. Ein QR-Code aus der Adressleiste des Browsers enthält den Schlüssel dann nicht mehr. Den Link aus der Startausgabe oder aus `derived/lan-key` nehmen.
- **Speicher:** Läuft der Server als Hintergrundprozess von Claude Code, kann Claude Code ihn bei knappem Arbeitsspeicher beenden. Dauerhaft in einem eigenen Fenster oder als Dienst starten.

### Neu bauen

```
pip install osmium                      # nur für PLZ, Gemeinden, Kreise
pip install numpy tifffile imagecodecs  # nur für --terrain
pip install shapely numpy               # nur für --addresses: Ort und PLZ aus Grenzflächen ergänzen
python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work --data /pfad/zu/LastbookData --terrain --addresses
```

Mehrere Gebiete in einer Karte, auch außerhalb Deutschlands:

```
python3 tools/build_region.py tools/regions/hessen.json tools/regions/bayern.json --label "Hessen und Bayern" --work ... --data ...
python3 tools/build_region.py tools/regions/hessen.json --geofabrik europe/france/alsace:Elsass --work ... --data ...
```

**Ganz Europa in Straßendetail ist nicht sinnvoll.** Jede Region bringt ihr ganzes Straßennetz mit; die US-Gesamtkarte des Originals liegt bei rund 80 GB, Europa läge in derselben Größenordnung oder darüber (nicht gemessen). Geofabrik bietet das benötigte GeoPackage außerdem nur für kleinere Gebiete an, ein großes Land muss aus seinen Teilen gebaut werden. Sinnvoll: Heimatregion plus Nachbarn in Detail, außen herum die Übersicht.

Übersicht um Hessen herum, damit die Karte herausgezoomt nicht leer ist. Dafür einmal einen Deutschland-Auszug filtern (`germany-latest.osm.pbf` von download.geofabrik.de/europe, knapp 5 GB; das Python-Paket `osmium` reicht, `osmium-tool` ist nicht nötig) und den Lauf mit `--overview` wiederholen:

```
python3 tools/filter_overview_osm.py germany-latest.osm.pbf germany-overview.osm.pbf
python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work --data /pfad/zu/LastbookData --terrain --addresses --overview germany-overview.osm.pbf
```

Mit einem Europa-Auszug geht dasselbe; der Download ist dann 35,5 GB groß (Stand 17.11.2026). Für Hessen reicht Deutschland.

Nur die Übersicht erneuern, ohne die ganze Region neu zu bauen (Server vorher beenden):

```
python3 tools/build_overview_osm.py germany-overview.osm.pbf ~/lastbook-work/out/map.sqlite --places ~/lastbook-work/out/places.sqlite --label Hessen
python3 -c "import sys, pathlib; sys.path[:0] = ['tools', '.']; import build_region as b; h = pathlib.Path.home(); w = h / 'lastbook-work'; b.install(w / 'out', h / 'LastbookData', w, 'HE', ['map.sqlite', 'places.sqlite', 'terrain.sqlite'])"
```

Ohne `--places` stehen die Städte der Übersicht nur auf der Karte, die Suche findet sie nicht (so bis 17.11.2026, 17:45 Uhr).

Lastbook muss dabei geschlossen sein. Ersetzte Dateien landen in `~/lastbook-work/replaced-<Zeit>/`.

### So startet der Heimserver

Ohne Docker (so läuft er am PC, Windows PowerShell):

```
cd $HOME\lastbook
python server.py --lan --no-index --data $HOME\LastbookData
```

Mit Docker:

```
LASTBOOK_DATA=/pfad/zu/LastbookData docker compose -f packaging/docker/compose.yaml up -d --build
docker compose -f packaging/docker/compose.yaml logs lastbook     # zeigt den Zugangsschlüssel
```

Auf dem iPhone einmal `http://<IP des Servers>:8890/?key=<Schlüssel>` öffnen. Der Server hat dafür bereits einen eigenen Modus (`--lan`): andere Geräte brauchen den Schlüssel einmal, danach gilt ein Cookie. Anfragen an einen Hostnamen statt an eine IP-Adresse lehnt er ab.

### Als Nächstes zu prüfen

1. Docker-Image bauen (auf einem Rechner mit Docker) und vom iPhone aus öffnen.
2. iPhone: Bedienung der Karte; „Zum Home-Bildschirm“ ohne HTTPS (Service Worker laufen auf iOS nur über HTTPS oder localhost).
3. Stimmt das Relief auf einen halben Bildpunkt zur Straßenkarte (Gipfel und Täler)? Im Browser unauffällig, nicht nachgemessen.
4. 3D-Ansicht mit echten Höhen.
5. Hilfepunkte jenseits der Landesgrenze fehlen (Apotheken, Kliniken in Mainz): Die Übersicht bringt nur Fernstraßen und Städte. Dafür Nachbarländer als eigene Regionen dazubauen; Platz und Bauzeit nicht gemessen.

### Bekannte Lücken in Etappe 1

- Die Ortssuche wird ersetzt, US-Ortsnamen sind danach nicht mehr enthalten.
- Das Kartenpanel nennt weiter die US-Basiskarte des Packs („Main roads ... for the whole US"); das stimmt, solange das Pack sie enthält.
- Die feste Quellenzeile der Karte nennt weiter US-Behörden; OpenStreetMap steht darin, Copernicus wird bei Bedarf angehängt.
- Adressen ohne `addr:city` oder `addr:postcode` in OSM bekommen Ort und PLZ aus der PLZ-Fläche und der Gemeinde, in der sie liegen (braucht `shapely`; ohne das Paket bleibt das Feld leer). In kreisfreien Städten wird der Kreisname genommen, sofern er nicht „kreis" enthält; außerhalb Hessens kann diese Faustregel danebenliegen.
- Eine Straße, die eine Regionsgrenze kreuzt, liegt in beiden Auszügen und wird doppelt gespeichert. Das Bild ändert sich nicht.

## Ziel

Lastbook (Offline-Überlebensbibliothek, MIT-Lizenz) soll zu Hause in Hessen bei Internetausfall nutzbar sein:

1. Eine **Detailkarte für Hessen** statt der US-Bundesstaatenkarte.
2. Betrieb als **Heimserver in Docker**, Zugriff per WLAN vom iPhone-Browser (als Web-App auf dem Homescreen).

Nutzer: privat. Sicher im Umgang mit Linux, Docker, YAML und Skripten.

## Nicht-Ziele

- Keine native iOS-App.
- Keine lokale KI auf dem Telefon.
- Keine Obst-/Weinbau-Ebene (`crops`), sie hat in Deutschland keine passende Quelle.
- Keine Übersetzung der englischen Bibliothek. Deutsche Guides und ein deutsches Dokumentenpack sind ein späteres, eigenes Vorhaben.
- Kein Pull Request ans Original. Gearbeitet wird in einem eigenen Fork.

## Was im Repo heute US-spezifisch ist

Geprüft durch Lesen des Codes, nicht durch Ausführen.

| Stelle | Befund |
|---|---|
| `tools/build_map.py` | Liest ein Geofabrik-GeoPackage (OSM), fest auf „SoCal" benannt. Format ist allgemein. |
| `tools/build_places.py` | Ortssuche aus USGS GNIS und Census-Gazetteers (ZIP-Codes, Countys) plus OSM-Orten. |
| `tools/build_terrain.py` | Höhenkacheln aus USGS 3DEP (30 m), Zoom 5–12, Terrain-RGB-PNG. |
| `tools/build_water.py` | Talsperren (USACE NID) und Gewässer (USGS NHD). |
| `tools/build_buildings.py` | Microsoft Building Footprints USA. |
| `tools/build_addresses.py`, `packaging/address_indexes.py` | Adressen aus Overture Maps, Standard „ganze USA". |
| `tools/build_coast.py` | Küstenlinie, für Hessen irrelevant. |
| `packaging/state_maps.py` | Feste Liste der US-Staaten; Upload auf `downloads.lastbook.org`. |
| `derived/packs/pack-spec.json` → `map_sets` | Staatsausschnitt = Box aus ZCTA-Mittelpunkten ± 0,15°. |
| `web/map.js` | `US`-Startausschnitt (Zeile 9), Höhenlinien und Höhenangaben in Fuß, „100 miles", Texte wie „outside the US", SoCal-Sonderfall. |
| `web/terrain3d.js` | Höhen in Fuß, „outside the US". |
| `engine/setup/install.py`, `engine/setup/api.py` | Prüfen eine Karte gegen `map-set.json` (`{name, files: {pfad: bytes}}`). Name ist „base", „us" oder Staatskürzel. |

Günstig: Die Karte wird aus einfachen SQLite-Dateien unter `derived/geo/` gezeichnet (`feat` + R*Tree, `poi`, `tile`, `bldg`), und `web/map.js` übernimmt eigene Grenzen (`st.bounds`). Das Format muss nicht geändert werden, nur die Zulieferer.

## Ansatz

Neue Builder neben die vorhandenen stellen, die dieselben Ausgabetabellen schreiben. Vorhandene US-Builder bleiben unverändert, damit der Fork mit dem Original zusammenführbar bleibt. Eine Region wird über eine kleine Konfiguration beschrieben (Name, Bounding-Box, Quellpfade), damit später andere Bundesländer möglich sind.

Verworfen: (a) die US-Builder direkt umschreiben – erschwert Updates vom Original; (b) die Karte durch fertige Vektorkacheln (z. B. PMTiles) ersetzen – würde Hilfepunkte, Ortssuche und 3D-Ansicht der App umgehen.

## Etappen

### Etappe 1 – Kern (zuerst, soll allein benutzbar sein)

- Straßen und Hilfepunkte für Hessen aus dem OSM-Auszug.
- Ortssuche aus OSM: Orte, Ortsteile, Gemeinden, Postleitzahlen.
- Oberfläche metrisch (m, km), Startausschnitt Hessen, US-Texte neutralisiert.
- `map-set.json` für die Region, so dass Setup und Prüfung sie annehmen.
- Docker-Setup für den Heimserver.

### Etappe 2 – Ausbau

- ~~Gelände, Höhenlinien, 3D aus einem freien Höhenmodell.~~ Als Code erledigt, siehe Stand.
- Gebäudeumrisse und Gewässerflächen kommen bereits mit der Straßenkarte aus Etappe 1. Offen sind nur Gebäudehöhen für die 3D-Ansicht.
- Gebäude aus OSM.
- Gewässer aus OSM.
- ~~Adresssuche aus OSM-Adressen.~~ Als Code erledigt, siehe Stand.
- ~~Europaweite Übersichtskarte für die weiten Zoomstufen.~~ Als Code erledigt (Fernstraßen und Städte; ohne Gewässer und Grenzen), siehe Stand.

## Datenquellen (vor Nutzung prüfen: URL, Lizenz, Aktualität)

- **OpenStreetMap** über Geofabrik, Auszug Hessen. Lizenz ODbL, Namensnennung in der Karte und auf der Quellenseite nötig. Prüfen, ob Geofabrik für Hessen das „free"-GeoPackage anbietet, das `build_map.py` erwartet; sonst aus `.osm.pbf` lesen (pyosmium wird im Repo bereits für die Küste verwendet).
- **Höhenmodell:** Copernicus DEM GLO-30 als Standard. Offene Landesdaten der hessischen Vermessungsverwaltung wären genauer; Verfügbarkeit und Lizenz erst prüfen.
- **Adressen:** OSM-Adresspunkte. Abdeckung im Zielgebiet stichprobenartig prüfen, bevor Aufwand hineinfließt.

## Heimserver

- `server.py` ist der Browser-Server (Port 8890), Start laut README mit Python ≥ 3.11 und Datenordner mit `library-data/catalog.json`.
- Zu klären: An welche Adresse bindet er, gibt es Host-/Origin-Prüfungen, schreibt er in den Datenordner? Er ist für den lokalen Rechner gedacht und hat keine Anmeldung. **Nur im Heimnetz freigeben, nicht ins Internet.**
- `web/` hat `manifest.webmanifest` und `sw.js`. Auf iOS funktionieren Service Worker nur über HTTPS oder localhost; prüfen, ob die Web-App ohne ihn sauber läuft, sonst lokales TLS (z. B. Reverse Proxy mit eigenem Zertifikat).
- Lokale KI ist optional (~17 GB Modell). Zunächst ohne.

## Rahmenbedingungen

- Python-Standardbibliothek bevorzugen, wie im Repo üblich; neue Abhängigkeiten begründen.
- Rohdaten nur lesen, nie verändern (Konvention des Repos).
- Tests: `app/tests/` und `packaging/test_pack_tools.py` müssen weiter grün sein. Neue Builder bekommen Tests mit kleinen Beispieldaten.
- Lizenzhinweise: `THIRD_PARTY_NOTICES.md` und die Quellenseite um neue Datenquellen ergänzen.
- Speicherbedarf für Hessen gemessen (17.11.2026): rund 20 GB Arbeitsordner einschließlich Pack-Zip, Deutschland-Auszug und ersetzter Dateien aus vier Läufen, rund 1,5 GB fertige Karte (Straßen mit Übersicht 905 MB, Gelände 372 MB, Adressen 172 MB, Orte 6 MB).

## Offene Fragen

Stand 17.11.2026:

1. Rechner: gebaut wird auf dem Gaming-PC (Windows 11), der Server läuft vorerst dort. Geplant ist ein Laptop als Hauptgerät (läuft mit Akku), der PC als Heimserver fürs WLAN. Für einen Stromausfall trägt nur ein Gerät mit eigener Stromversorgung. **Offen:** dauerhafter Start des Servers ohne offenes Fenster.
2. Bibliothekspaket: Small (7,69 GB).
3. Hessen im Detail, Deutschland als Übersicht. **Offen:** Nachbarländer im Detail (Hilfepunkte jenseits der Grenze).

## Erste Schritte für Claude Code

1. Dieses Dokument und `README.md`, `docs/SETUP-API.md`, `content/SCHEMA.md` lesen.
2. Die Befunde der Tabelle oben am Code bestätigen, vor allem `engine/setup/install.py` (welche Kartennamen zulässig sind) und das Netzwerkverhalten von `server.py`.
3. Die offenen Fragen stellen.
4. Einen Umsetzungsplan für Etappe 1 vorlegen und freigeben lassen, erst dann bauen.
5. Früh mit echten Hessen-Daten testen: zuerst ein kleiner Ausschnitt (z. B. Landkreis Gießen), dann das ganze Land.

## Abnahme Etappe 1

- Karte öffnet auf Hessen; Straßen und Ortsnamen sind bis auf Straßenebene lesbar.
- Suche findet eine Gemeinde, einen Ortsteil und eine Postleitzahl.
- Kliniken, Apotheken und Wasserstellen erscheinen als Hilfepunkte.
- Entfernungen und Höhen stehen in metrischen Einheiten.
- `docker compose up` startet den Server; das iPhone erreicht ihn im WLAN ohne Internetverbindung.
