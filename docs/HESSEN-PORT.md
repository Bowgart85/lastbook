# Übergabe: Lastbook für Hessen/Deutschland + Heimserver

Übergabedokument für Claude Code. Stand: 2026-11-17. Basis: `Immortal-Protocols/lastbook`, Release 1.1.8, flacher Klon vom selben Tag.

## Stand (2026-11-17, Branch `hessen-port`)

Etappe 1 ist als Code vorhanden und mit kleinen Testdaten geprüft. **Mit echten Hessen-Daten ist noch nichts gelaufen.**

| Teil | Datei | Geprüft |
|---|---|---|
| Straßenkarte für beliebige Region | `tools/build_map.py` (neue Optionen `--source`, `--as-of`, `--bounds`; ohne Optionen unverändert) | Test + Server liefert Kacheln |
| Ortssuche aus OSM: Orte, Hilfepunkte, PLZ, Gemeinden, Kreise; „Giessen" findet „Gießen" | `tools/build_places_osm.py` | Test + `/api/places` |
| Ein Befehl: laden, bauen, einspielen, `map-set.json` schreiben | `tools/build_region.py`, `tools/regions/hessen.json` | mit lokalen Testdateien; **Download nicht** |
| Metrische Anzeige außerhalb der USA (Maßstab, Höhen, Höhenlinien, 3D) | `web/map.js`, `web/terrain3d.js` | nur Syntaxprüfung, **nicht im Browser** |
| Kartenpanel nennt die Ortsdaten der Region | `server.py` (`pack_datasets`) | `/api/map/info` |
| Heimserver | `packaging/docker/Dockerfile`, `compose.yaml`, `.dockerignore` | Server lief mit genau diesen Dateien und Abhängigkeiten; **Image nicht gebaut** |
| Tests | `app/tests/test_region_map.py` (5 Tests) | grün |

Bestehende Tests: 319 gelaufen, 1 Fehler in `test_setup.Recommend.test_hardware_here`. Der Test erwartet macOS oder Windows und schlägt unter Linux auch ohne diese Änderungen fehl.

### So wird die Karte gebaut

```
pip install osmium                      # nur für PLZ, Gemeinden, Kreise
python3 tools/build_region.py tools/regions/hessen.json --work ~/lastbook-work --data /pfad/zu/LastbookData
```

Lastbook muss dabei geschlossen sein. Ersetzte Dateien landen in `~/lastbook-work/replaced-<Zeit>/`.

### So startet der Heimserver

```
LASTBOOK_DATA=/pfad/zu/LastbookData docker compose -f packaging/docker/compose.yaml up -d --build
docker compose -f packaging/docker/compose.yaml logs lastbook     # zeigt den Zugangsschlüssel
```

Auf dem iPhone einmal `http://<IP des Servers>:8890/?key=<Schlüssel>` öffnen. Der Server hat dafür bereits einen eigenen Modus (`--lan`): andere Geräte brauchen den Schlüssel einmal, danach gilt ein Cookie. Anfragen an einen Hostnamen statt an eine IP-Adresse lehnt er ab.

### Als Nächstes zu prüfen (mit echten Daten)

1. Stimmen die beiden Geofabrik-Adressen in `tools/regions/hessen.json`? Sie sind nicht verifiziert.
2. Laufzeit und Speicher von `build_region.py` für ganz Hessen. Der PLZ-Schritt baut alle Flächen des Auszugs zusammen und kann lange dauern; falls zu langsam, vorher mit `osmium tags-filter` auf `boundary=*` eingrenzen.
3. Karte im Browser ansehen: Startausschnitt, Beschriftung, Maßstab in km, Hilfepunkte.
4. Docker-Image bauen und vom iPhone aus öffnen. Offen ist, ob die Web-App ohne HTTPS sauber läuft (Service Worker).
5. Basiskarte: Ein Pack bringt eine grobe Welt- und US-Karte mit. Ob sie Deutschland in den weiten Zoomstufen brauchbar zeigt, ist ungeprüft.

### Bekannte Lücken in Etappe 1

- Die Ortssuche wird ersetzt, US-Ortsnamen sind danach nicht mehr enthalten.
- Texte im Kartenpanel nennen weiter die US-Basiskarte („Main roads ... for the whole US").
- Die Quellenzeile der Karte nennt weiter US-Behörden; OpenStreetMap steht bereits darin.
- `THIRD_PARTY_NOTICES.md` ist noch nicht ergänzt.

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

- Gelände, Höhenlinien, 3D aus einem freien Höhenmodell.
- Gebäude aus OSM.
- Gewässer aus OSM.
- Adresssuche aus OSM-Adressen.

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
- Speicherbedarf geschätzt, nicht gemessen: 10–20 GB Zwischendaten, 1–2 GB fertige Karte.

## Offene Fragen

1. Auf welchem Rechner wird gebaut, auf welchem läuft der Server (Linux-Box, Mini-PC, NAS)?
2. Welches Bibliothekspaket (Small ≈ 8 GB, Medium, All)?
3. Nur Hessen oder mit Randstreifen in die Nachbarländer?

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
