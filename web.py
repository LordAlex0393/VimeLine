import os
import sqlite3
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "vime_stats.db")

CUSTOM_NAMES = {
    "lobby": "Лобби",
    "sololeveling": "Solo Leveling",
    "skyblock": "SkyBlock",
    "prison": "Prison",
    "prison-lite": "Prison Lite",
    "luckywars": "Lucky Wars",
    "farm": "MyLittleFarm",
    "stealacreature": "Steal a Creature",
    "bridge": "The Bridge",
    "petsimulator": "Pets GO",
    "deathrun": "DeathRun",
    "ann": "Annihilation",
    "bb": "BuildBattle",
    "bp": "BlockParty",
    "bw": "BedWars",
    "bwhype": "BedWars Hype",
    "cp": "ClashPoint",
    "duels": "Duels",
    "gg": "GunGame",
    "hg": "HungerGames",
    "kpvp": "KitPvP",
    "mw": "MobWars",
    "sw": "SkyWars",
    "swt": "SkyWars Team",
    "murder": "Murder Mystery",
    "jumpleague": "Jump League",
    "turfwars": "Turf Wars",
    "sheep": "SheepWars",
    "tntrun": "TNT Run",
    "tnttag": "TNT Tag",
    "zombieclaus": "Царство Зомби Мороза",
    "whitecold": "Белый холод",
    "squidgame": "Squid Game",
    "hide": "Hide and Seek",
    "speedbuilders": "Speed Builders",
    "teamfortress": "Team Fortress",
    "fallguys": "Fall Guys",
    "eggwars": "Egg Wars",
    "battlebox": "BattleBox",
    "rodwars": "Rod Wars",
    "randomrush": "Random Rush",
    "coingames": "Coin Games",
    "fireballfight": "Fireball Fight",
    "css": "Custom Steve Survival",
    "cor": "Chaos of Reign",
    "chm": "Chm",
    "bingo": "Bingo",
}


def load_translations():
    mapping = dict(CUSTOM_NAMES)
    for _ in range(5):
        try:
            resp = requests.get("https://vimeworld.com", timeout=10)
            resp.raise_for_status()
            games = resp.json().get("games", {})
            for key, info in games.items():
                name = info.get("name", key)
                if key == "bwhype":
                    name = f"{name} (Hype)"
                mapping[key] = name
                mapping[key.replace("_", "-")] = name
            print("Русская локализация успешно загружена!")
            return mapping
        except Exception:
            time.sleep(2)
    print("Локализация не загружена, используем базовую.")
    return mapping



TRANSLATIONS = load_translations()


def get_mode_name(key):
    return TRANSLATIONS.get(key) or TRANSLATIONS.get(key.replace("-", "_")) or key


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/dashboard")
def api_dashboard():
    if not os.path.exists(DB_FILE):
        return jsonify({"error": "База данных еще не найдена."}), 404

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT timestamp, total FROM total_online ORDER BY timestamp ASC")
        total_rows = cur.fetchall()

        if not total_rows:
            return jsonify({"empty": True})

        timestamps = [r["timestamp"] for r in total_rows]
        totals = [r["total"] for r in total_rows]
        current_total = totals[-1]
        last_update = timestamps[-1]

        max_all_idx = totals.index(max(totals))
        peak_all = {"value": totals[max_all_idx], "time": timestamps[max_all_idx]}

        cutoff_24h = (datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S") - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        recent_24h = [r["total"] for r in total_rows if r["timestamp"] >= cutoff_24h]
        peak_24h = max(recent_24h) if recent_24h else current_total
        avg_24h = round(sum(recent_24h) / len(recent_24h)) if recent_24h else current_total

        cur.execute("SELECT timestamp, mode_key, count FROM mode_online ORDER BY timestamp ASC")
        mode_rows = cur.fetchall()

        time_index = {t: i for i, t in enumerate(timestamps)}
        modes_series = {}
        mode_peaks = {}

        for r in mode_rows:
            mk, ts, cnt = r["mode_key"], r["timestamp"], r["count"]
            if mk not in modes_series:
                modes_series[mk] = list([0] * len(timestamps))
                mode_peaks[mk] = 0
            idx = time_index.get(ts)
            if idx is not None:
                modes_series[mk][idx] = cnt
            if cnt > mode_peaks[mk]:
                mode_peaks[mk] = cnt

        modes_info = []
        for mk, series in modes_series.items():
            modes_info.append({
                "key": mk,
                "name": get_mode_name(mk),
                "current": series[-1],
                "peak": mode_peaks[mk],
                "series": series
            })
        modes_info.sort(key=lambda x: (x["current"], x["peak"]), reverse=True)

        cur.execute("""
            SELECT strftime('%H', timestamp) as hour, ROUND(AVG(total)) as avg_total
            FROM total_online GROUP BY hour ORDER BY hour ASC
        """)
        hourly_rows = cur.fetchall()
        hourly = {
            "hours": [f"{r['hour']}:00" for r in hourly_rows],
            "values": [int(r["avg_total"]) for r in hourly_rows]
        }

    return jsonify({
        "empty": False,
        "summary": {
            "current": current_total,
            "last_update": last_update,
            "peak_all": peak_all,
            "peak_24h": peak_24h,
            "avg_24h": avg_24h,
            "top_mode": modes_info[0] if modes_info else {"name": "-", "current": 0}
        },
        "timestamps": timestamps,
        "totals": totals,
        "modes": modes_info,
        "hourly": hourly
    })


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/echarts.min.js")
def serve_echarts():
    return send_from_directory(BASE_DIR, "echarts.min.js")


if __name__ == "__main__":
    print("Дашборд запущен: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
