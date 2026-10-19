
import json

with open('laguna_municipality_geodata.geojson', encoding='utf-8') as fh:
    g = json.load(fh)

s, w, n, e = 90, 180, -90, -180

def walk(c):
  global s, w, n, e
  if isinstance(c[0], float):
    w = min(w, c[0])
    s = min(s, c[1])
    e = max(e, c[0])
    n = max(n, c[1])
  else:
     for p in c:
        walk(p)

for f in g['features']:
    walk(f['geometry']['coordinates'])

print(f"L.latLngBounds([{round(s,4)}, {round(w,4)}], [{round(n,4)}, {round(e,4)}])")