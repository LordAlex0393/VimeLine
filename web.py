import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "vime_stats.db")

MODE_NAMES = {
    "lobby": "Лобби", "sololeveling": "Solo Leveling",
    "skyblock": "SkyBlock", "prison": "Prison", "prison-lite": "Prison Lite",
    "luckywars": "Lucky Wars", "farm": "MyLittleFarm",
    "stealacreature": "Steal a Creature", "bridge": "The Bridge",
    "petsimulator": "Pets GO", "deathrun": "DeathRun", "ann": "Annihilation",
    "bb": "BuildBattle", "bp": "BlockParty", "bw": "BedWars",
    "bwhype": "BedWars Hype", "cp": "ClashPoint", "duels": "Duels",
    "gg": "GunGame", "hg": "HungerGames", "kpvp": "KitPvP",
    "mw": "MobWars", "sw": "SkyWars", "swt": "SkyWars Team",
    "murder": "Murder Mystery", "jumpleague": "Jump League",
    "turfwars": "Turf Wars", "sheep": "SheepWars", "tntrun": "TNT Run",
    "tnttag": "TNT Tag", "zombieclaus": "Царство Зомби Мороза",
    "whitecold": "Белый холод", "squidgame": "Squid Game",
    "hide": "Hide and Seek", "speedbuilders": "Speed Builders",
    "teamfortress": "Team Fortress", "fallguys": "Fall Guys",
    "eggwars": "Egg Wars", "battlebox": "BattleBox", "rodwars": "Rod Wars",
    "randomrush": "Random Rush", "coingames": "Coin Games",
    "fireballfight": "Fireball Fight", "css": "Custom Steve Survival",
    "cor": "Chaos of Reign", "chm": "Chm", "bingo": "Bingo",
}


def get_mode_name(key):
    return MODE_NAMES.get(key) or MODE_NAMES.get(key.replace("-", "_")) or key


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/dashboard")
def api_dashboard():
    if not os.path.exists(DB_FILE):
        return jsonify({"error": "База данных еще не найдена."}), 404

    start_q = request.args.get("start", "").strip()
    end_q = request.args.get("end", "").strip()

    where_clauses = []
    params = []
    if start_q:
        where_clauses.append("timestamp >= ?")
        params.append(start_q + " 00:00:00")
    if end_q:
        where_clauses.append("timestamp <= ?")
        params.append(end_q + " 23:59:59")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT timestamp, total FROM total_online {where_sql} ORDER BY timestamp ASC", params)
        total_rows = cur.fetchall()

        if not total_rows:
            return jsonify({"empty": True})

        timestamps = [r["timestamp"] for r in total_rows]
        totals = [r["total"] for r in total_rows]
        current_total = totals[-1]
        last_update = timestamps[-1]

        # Пик и минимум за выбранный период
        max_idx = totals.index(max(totals))
        min_idx = totals.index(min(totals))
        peak_period = {"value": totals[max_idx], "time": timestamps[max_idx]}
        min_period = {"value": totals[min_idx], "time": timestamps[min_idx]}
        avg_period = round(sum(totals) / len(totals))

        # Дневные пики (максимум за каждый день)
        daily_max = {}
        for r in total_rows:
            day = r["timestamp"][:10]
            val = r["total"]
            if day not in daily_max or val > daily_max[day]["val"]:
                daily_max[day] = {"val": val, "time": r["timestamp"]}

        daily_days = sorted(daily_max.keys())
        daily_vals = [daily_max[d]["val"] for d in daily_days]

        best_day = max(daily_days, key=lambda d: daily_max[d]["val"])
        worst_day = min(daily_days, key=lambda d: daily_max[d]["val"])
        # 2. Данные по режимам за выбранный период
        cur.execute(f"SELECT timestamp, mode_key, count FROM mode_online {where_sql} ORDER BY timestamp ASC", params)
        mode_rows = cur.fetchall()

        time_index = {t: i for i, t in enumerate(timestamps)}
        modes_series = {}

        for r in mode_rows:
            mk, ts, cnt = r["mode_key"], r["timestamp"], r["count"]
            if mk not in modes_series:
                modes_series[mk] = [0] * len(timestamps)
            idx = time_index.get(ts)
            if idx is not None:
                modes_series[mk][idx] = cnt

        modes_info = []
        for mk, series in modes_series.items():
            peak_val = max(series) if series else 0
            peak_idx = series.index(peak_val) if series else 0
            avg_val = round(sum(series) / len(series), 1) if series else 0
            modes_info.append({
                "key": mk,
                "name": get_mode_name(mk),
                "current": series[-1] if series else 0,
                "peak": peak_val,
                "peak_time": timestamps[peak_idx] if timestamps else "",
                "avg": avg_val,
                "series": series
            })
        modes_info.sort(key=lambda x: (x["current"], x["peak"]), reverse=True)

        # 3. Тепловая карта (День недели 0..6 x Час 00..23)
        heatmap_sum = {}
        heatmap_cnt = {}
        for r in total_rows:
            dt = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
            key = (dt.weekday(), dt.hour)
            heatmap_sum[key] = heatmap_sum.get(key, 0) + r["total"]
            heatmap_cnt[key] = heatmap_cnt.get(key, 0) + 1

        heatmap_data = []
        for (wd, hr), s_val in heatmap_sum.items():
            heatmap_data.append({
                "hour": hr,
                "day": wd,
                "val": round(s_val / heatmap_cnt[(wd, hr)])
            })


    return jsonify({
        "empty": False,
        "summary": {
            "current": current_total,
            "last_update": last_update,
            "peak_period": peak_period,
            "min_period": min_period,
            "avg_period": avg_period,
            "best_day": {"date": best_day, "value": daily_max[best_day]["val"], "time": daily_max[best_day]["time"]},
            "worst_day": {"date": worst_day, "value": daily_max[worst_day]["val"], "time": daily_max[worst_day]["time"]},
            "top_mode": modes_info[0] if modes_info else {"name": "-", "current": 0}
        },
        "timestamps": timestamps,
        "totals": totals,
        "daily": {"days": daily_days, "values": daily_vals},
        "modes": modes_info,
        "heatmap": heatmap_data
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
