"""교통 센서 자리의 도로 선을 만든다 → src/web/src/components/trafficRoads.ts (10/12 오너: 도로를 혼잡도 색으로 칠하기).

우리 데이터는 센서 4곳의 지점 값뿐이라, 센서가 놓인 길(929번 호미로·구룡포길)만 칠한다.
- 센서를 차례로 잇는 도로 경로(OpenStreetMap 도로망에서 최단 경로)를 찾는다.
- 이웃한 두 센서 사이는 가운데에서 갈라 각 반쪽을 가까운 센서 몫으로(색을 섞어 재지 않은 값을 만들지 않는다).
- 맨 바깥 센서 바깥쪽은 EXT_M 만큼만 길을 따라 늘린다.
도로 출처: OpenStreetMap(ⓒ OpenStreetMap contributors, ODbL). 센서 좌표: 서버 /api/traffic/sensors (E-UM).

실행: uv run python scripts/build_traffic_roads.py  (서버가 8000에서 돌고 있어야 센서 좌표를 읽는다. 없으면 아래 기본값)
"""
from __future__ import annotations

import heapq
import json
import math
import urllib.request
from pathlib import Path

BBOX = (129.5440, 35.9830, 129.5660, 35.9930)  # 서, 남, 동, 북
OSM_URL = "https://api.openstreetmap.org/api/0.6/map.json?bbox={},{},{},{}".format(*BBOX)
DRIVE = {"secondary", "tertiary", "secondary_link", "tertiary_link", "unclassified", "residential"}
MAIN = {"secondary", "tertiary"}  # 센서를 붙이는 길
EXT_M = 150
# 길을 따라 늘어선 차례(서 → 동). /api/traffic/sensors 를 못 읽을 때의 좌표(10/12 확인값)
ORDER = ["교통센서2", "교통센서1", "교통센서3", "교통센서4"]
FALLBACK = {"교통센서2": (35.985863, 129.548065), "교통센서1": (35.986351, 129.549484),
            "교통센서3": (35.989895, 129.555084), "교통센서4": (35.98999, 129.562576)}
OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "components" / "trafficRoads.ts"


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = (a[0] - b[0]) * 110574
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dx, dy)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "9ryongpo-hackathon/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def sensors() -> dict[str, tuple[float, float]]:
    try:
        d = get_json("http://localhost:8000/api/traffic/sensors")
        return {s["name"]: (s["lat"], s["lon"]) for s in d["sensors"]}
    except Exception as e:  # 서버가 꺼져 있으면 확인해 둔 좌표로
        print(f"센서 좌표를 서버에서 못 읽어 기본값 사용: {type(e).__name__}")
        return FALLBACK


def main() -> None:
    d = get_json(OSM_URL)
    pos = {e["id"]: (e["lat"], e["lon"]) for e in d["elements"] if e["type"] == "node"}
    graph: dict[int, list[tuple[int, float]]] = {}
    main_nodes: set[int] = set()
    for w in d["elements"]:
        hw = w.get("tags", {}).get("highway") if w["type"] == "way" else None
        if hw not in DRIVE:
            continue
        ns = w["nodes"]
        if hw in MAIN:
            main_nodes.update(ns)
        for a, b in zip(ns, ns[1:]):
            c = dist(pos[a], pos[b])
            graph.setdefault(a, []).append((b, c))
            graph.setdefault(b, []).append((a, c))

    def shortest(s: int, t: int) -> list[int]:
        best, prev, q = {s: 0.0}, {}, [(0.0, s)]
        while q:
            c, u = heapq.heappop(q)
            if u == t:
                break
            if c > best.get(u, 1e18):
                continue
            for v, w in graph.get(u, []):
                if c + w < best.get(v, 1e18):
                    best[v], prev[v] = c + w, u
                    heapq.heappush(q, (c + w, v))
        out = [t]
        while out[-1] != s:
            out.append(prev[out[-1]])
        return out[::-1]

    def extend(path: list[int], at_start: bool) -> list[int]:
        """끝에서 같은 방향(가장 덜 꺾이는 길)으로 EXT_M 만큼 이어 간다."""
        seq = path[::-1] if at_start else path[:]
        used, gone = set(path), 0.0
        while gone < EXT_M:
            u, p = seq[-1], seq[-2]
            h0 = math.atan2(pos[u][0] - pos[p][0], pos[u][1] - pos[p][1])
            cand = [(abs((math.atan2(pos[v][0] - pos[u][0], pos[v][1] - pos[u][1]) - h0 + math.pi) % (2 * math.pi) - math.pi), v, w)
                    for v, w in graph.get(u, []) if v not in used]
            if not cand:
                break
            turn, v, w = min(cand)
            if turn > math.radians(60):  # 큰 갈림길에서 꺾어야 하면 멈춘다
                break
            seq.append(v); used.add(v); gone += w
        return seq[::-1] if at_start else seq

    sp = sensors()
    snap = {n: min(main_nodes, key=lambda k: dist(pos[k], sp[n])) for n in ORDER}
    for n in ORDER:
        print(f"{n}: 도로까지 {dist(pos[snap[n]], sp[n]):.0f}m")
    route = [snap[ORDER[0]]]
    for a, b in zip(ORDER, ORDER[1:]):
        route += shortest(snap[a], snap[b])[1:]
    route = extend(extend(route, at_start=True), at_start=False)

    pts = [pos[n] for n in route]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + dist(a, b))
    at = {n: cum[route.index(snap[n])] for n in ORDER}
    cuts = [0.0] + [(at[a] + at[b]) / 2 for a, b in zip(ORDER, ORDER[1:])] + [cum[-1]]

    def point(x: float) -> tuple[float, float]:
        for i in range(1, len(cum)):
            if cum[i] >= x:
                t = (x - cum[i - 1]) / ((cum[i] - cum[i - 1]) or 1)
                return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t)
        return pts[-1]

    roads = []
    for i, n in enumerate(ORDER):
        lo, hi = cuts[i], cuts[i + 1]
        seg = [point(lo)] + [p for p, c in zip(pts, cum) if lo < c < hi] + [point(hi)]
        roads.append({"sensor": n, "path": [[round(a, 6), round(b, 6)] for a, b in seg]})
        print(f"{n}: {hi - lo:.0f}m")

    body = ",\n".join(f"  {{ sensor: '{r['sensor']}', path: {json.dumps(r['path'])} }}" for r in roads)
    OUT.write_text(
        "// 자동 생성: src/server/scripts/build_traffic_roads.py — 손으로 고치지 말 것\n"
        "// 교통 센서가 놓인 길을 센서마다 나눈 선(이웃 센서 사이는 가운데에서 가름, 양 끝은 길 따라 150m).\n"
        "// 도로: ⓒ OpenStreetMap contributors (ODbL)\n"
        f"export const TRAFFIC_ROADS: {{ sensor: string; path: [number, number][] }}[] = [\n{body},\n]\n",
        encoding="utf-8")
    print(f"썼다: {OUT}")


if __name__ == "__main__":
    main()
