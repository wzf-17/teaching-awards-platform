# -*- coding: utf-8 -*-
import os
import re
import json
import time
import uuid
from pathlib import Path
from datetime import datetime

import requests
from flask import Flask, jsonify, request, Response, stream_with_context
import mysql.connector
from mysql.connector import Error
from flask_cors import CORS

# =========================
# 简单内存会话：开发期够用（生产再换 Redis/DB）
# =========================
CHAT_SESSIONS = {}
# 结构：{ session_id: [ {"role":"user/assistant/system","content":"...","ts":"..."} , ... ] }
CHAT_CONTEXTS = {}


# =========================
# DeepSeek 调用
# =========================
def deepseek_chat(messages, model=None, temperature=0.2, max_tokens=900, timeout=60, retries=2):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY（请在启动 Flask 的同一个 PowerShell 窗口里 setx / $env:DEEPSEEK_API_KEY=...）")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
    }

    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

            if resp.status_code != 200:
                text = (resp.text or "")[:800]
                raise RuntimeError(f"DeepSeek API HTTP {resp.status_code}: {text}")

            data = resp.json() if resp.content else {}
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"DeepSeek 返回异常：缺少 choices，raw={str(data)[:800]}")

            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").strip()
            if not content:
                content = (choices[0].get("text") or "").strip()
            if not content:
                raise RuntimeError(f"DeepSeek 返回空内容，raw={str(data)[:800]}")

            return content

        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
            else:
                break

    raise last_err


def split_stream_text(text: str, max_chunk_size: int = 12):
    text = str(text or "")
    if not text:
        return

    buffer = ""
    punctuation = set("，。！？；：,.!?;:）)】]、\n")

    for ch in text:
        buffer += ch

        if ch == "\n":
            yield buffer
            buffer = ""
            continue

        if len(buffer) >= max_chunk_size or ch in punctuation:
            yield buffer
            buffer = ""

    if buffer:
        yield buffer

def deepseek_chat_stream(messages, model=None, temperature=0.2, max_tokens=900, timeout=120, retries=1):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": True,
    }

    last_err = None

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
                stream=True,
            )

            if resp.status_code != 200:
                text = (resp.text or "")[:800]
                raise RuntimeError(f"DeepSeek API HTTP {resp.status_code}: {text}")

            resp.encoding = "utf-8"
            buffer = ""

            # 改成 iter_content 手动切行，尽可能降低 requests / urllib3 的内部缓冲影响。
            for raw_chunk in resp.iter_content(chunk_size=1, decode_unicode=True):
                if not raw_chunk:
                    continue

                buffer += raw_chunk

                while "\n" in buffer:
                    raw_line, buffer = buffer.split("\n", 1)
                    line = raw_line.strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        return

                    try:
                        data = json.loads(data_str)
                    except Exception:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    content = delta.get("content") or ""
                    if content:
                        for piece in split_stream_text(content):
                            yield piece

            return

        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
            else:
                break

    raise last_err

# =========================
# Flask App 基础配置
# =========================
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False
CORS(app)

# =========================
# DB 连接：环境变量优先，未设置时使用本地开发默认值。
# =========================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "000000"),
    "database": os.getenv("DB_NAME", "teaching_awards"),
    "charset": "utf8mb4",
    "autocommit": True,
}


def _connect_db():
    return mysql.connector.connect(**DB_CONFIG)


db = _connect_db()

TABLE = "zhejiang_awards"
MASTER_TABLE = "awards_master"
MATERIAL_LINKS_TABLE = "material_link_library"
DEFAULT_PROVINCE = "浙江省"
DEFAULT_YEARS = [2021, 2025]

PROVINCE_CONFIG = {
    "浙江省": {
        "display_name": "浙江省",
        "detail_table": "zhejiang_awards",
        "title_prefix": "浙江",
        "available_qtypes": [
            "geo_dist",
            "discipline",
            "org_level",
            "theme_table",
            "completion_mode",
            "collab",
            "wordcloud",
            "award_level",
        ],
    },
    "上海市": {
        "display_name": "上海市",
        "detail_table": "shanghai_awards",
        "title_prefix": "上海",
        "available_qtypes": [
            "geo_dist",
            "discipline",
            "org_level",
            "award_level",
            "collab",
            "completion_mode",
        ],
    },
    "陕西省": {
        "display_name": "陕西省",
        "detail_table": "shaanxi_awards",
        "title_prefix": "陕西",
        "available_qtypes": [
            "geo_dist",
            "discipline",
            "org_level",
            "award_level",
            "collab",
            "completion_mode",
        ],
    },
    "湖北省": {
        "display_name": "湖北省",
        "detail_table": "hubei_awards",
        "title_prefix": "湖北",
        "available_qtypes": [
            "geo_dist",
            "discipline",
            "org_level",
            "award_level",
            "collab",
            "completion_mode",
        ],
    },
    "湖南省": {
        "display_name": "湖南省",
        "detail_table": "hunan_awards",
        "title_prefix": "湖南",
        "available_qtypes": [
            "geo_dist",
            "discipline",
            "org_level",
            "award_level",
            "collab",
            "completion_mode",
        ],
    },
}

PROVINCE_ALIASES = {
    "浙江": "浙江省",
    "浙江省": "浙江省",
    "上海": "上海市",
    "上海市": "上海市",
    "陕西": "陕西省",
    "陕西省": "陕西省",
    "湖北": "湖北省",
    "湖北省": "湖北省",
    "湖南": "湖南省",
    "湖南省": "湖南省",
}


def normalize_province_name(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_PROVINCE
    return PROVINCE_ALIASES.get(raw, raw)


def get_province_config(province=None) -> dict:
    canonical = normalize_province_name(province)
    return PROVINCE_CONFIG.get(canonical, PROVINCE_CONFIG[DEFAULT_PROVINCE])


def detail_table_for_province(province=None) -> str:
    return get_province_config(province)["detail_table"]


def province_title_prefix(province=None) -> str:
    return get_province_config(province)["title_prefix"]


def province_display_name(province=None) -> str:
    return get_province_config(province)["display_name"]


def get_available_qtypes(province=None) -> list[str]:
    return list(get_province_config(province).get("available_qtypes") or [])


def province_supports_qtype(province, qtype: str) -> bool:
    return qtype in get_available_qtypes(province)


def get_cursor():
    """获取 dict 游标，并尝试自动重连"""
    global db
    try:
        db.ping(reconnect=True, attempts=2, delay=0)
    except Exception:
        try:
            db.close()
        except Exception:
            pass
        db = _connect_db()
    return db.cursor(dictionary=True)


def _fetchone(sql, params=None):
    global db
    last_err = None
    for _ in range(2):
        cur = get_cursor()
        try:
            cur.execute(sql, params or [])
            return cur.fetchone()
        except Exception as e:
            last_err = e
            try:
                db.close()
            except Exception:
                pass
            db = _connect_db()
        finally:
            try:
                cur.close()
            except Exception:
                pass
    raise last_err


def _fetchall(sql, params=None):
    global db
    last_err = None
    for _ in range(2):
        cur = get_cursor()
        try:
            cur.execute(sql, params or [])
            return cur.fetchall()
        except Exception as e:
            last_err = e
            try:
                db.close()
            except Exception:
                pass
            db = _connect_db()
        finally:
            try:
                cur.close()
            except Exception:
                pass
    raise last_err


def _execute(sql, params=None):
    global db
    last_err = None
    for _ in range(2):
        cur = get_cursor()
        try:
            cur.execute(sql, params or [])
            return cur.rowcount
        except Exception as e:
            last_err = e
            try:
                db.close()
            except Exception:
                pass
            db = _connect_db()
        finally:
            try:
                cur.close()
            except Exception:
                pass
    raise last_err


def ensure_material_links_table():
    _execute(
        f"""
        CREATE TABLE IF NOT EXISTS `{MATERIAL_LINKS_TABLE}` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `province` VARCHAR(32) NOT NULL,
            `year` INT NOT NULL,
            `award_level` VARCHAR(32) NOT NULL,
            `award_name` VARCHAR(512) NOT NULL,
            `material_url` VARCHAR(1024) NOT NULL,
            `is_valid` TINYINT(1) NOT NULL DEFAULT 1,
            `remark` VARCHAR(255) NULL,
            PRIMARY KEY (`id`),
            KEY `idx_material_links_query` (`province`, `year`, `award_level`, `is_valid`),
            KEY `idx_material_links_name` (`award_name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


# =========================
# RAG 配置文件路径（qtype specs）
# =========================
RAG_DIR = os.path.join(os.path.dirname(__file__), "config")
QTYPE_SPECS_PATH = os.path.join(RAG_DIR, "qtype_specs.json")


def load_qtype_specs():
    p = Path(QTYPE_SPECS_PATH)
    if not p.exists():
        raise FileNotFoundError(f"找不到 qtype 配置文件：{p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# 基础统计/摘要工具
# =========================
def _pct(a, b):
    if not b:
        return 0.0
    return round(a * 100.0 / b, 2)


def _build_dist_summary(labels, values, top_n=5):
    total = int(sum(values))
    pairs = list(zip(labels, values))
    pairs.sort(key=lambda x: x[1], reverse=True)

    top = [{"label": lab, "count": int(v), "percent": _pct(v, total)} for lab, v in pairs[:top_n]]
    others_count = int(sum(v for _, v in pairs[top_n:]))
    others_percent = _pct(others_count, total)
    top1_percent = top[0]["percent"] if top else 0.0

    return {
        "total": total,
        "top": top,
        "others": {"count": others_count, "percent": others_percent},
        "top1_percent": top1_percent
    }


# =========================
# 表结构探测（用于自动兼容你的汇总表真实字段名）
# =========================
def get_table_columns(db_conn, table_name, schema_name):
    cur = db_conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        """,
        (schema_name, table_name),
    )
    rows = cur.fetchall()
    cur.close()
    cols = [r["COLUMN_NAME"] for r in rows]
    types = {r["COLUMN_NAME"]: r["DATA_TYPE"] for r in rows}
    return cols, types


def _schema_name():
    return db.database if hasattr(db, "database") else None


def _table_exists(table_name: str) -> bool:
    schema = _schema_name()
    if not schema:
        return False
    row = _fetchone(
        "SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        [schema, table_name],
    )
    return bool(row and int(row["c"]) > 0)


def _col_exists(table_name: str, col_name: str) -> bool:
    schema = _schema_name()
    if not schema:
        return False
    row = _fetchone(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        [schema, table_name, col_name],
    )
    return bool(row and int(row["c"]) > 0)


def has_master_data_for_province(province=None) -> bool:
    canonical = normalize_province_name(province)
    if not _table_exists(MASTER_TABLE):
        return False
    row = _fetchone(
        f"SELECT COUNT(*) AS c FROM `{MASTER_TABLE}` WHERE province=%s",
        [canonical],
    )
    return bool(row and int(row["c"]) > 0)


def available_years_for_province(province=None) -> list[int]:
    canonical = normalize_province_name(province)
    if has_master_data_for_province(canonical):
        rows = _fetchall(
            f"SELECT award_year AS year_value FROM `{MASTER_TABLE}` WHERE province=%s AND award_year IS NOT NULL GROUP BY award_year ORDER BY award_year",
            [canonical],
        )
        years = []
        for row in rows:
            try:
                years.append(int(row["year_value"]))
            except Exception:
                continue
        return years

    table_name = detail_table_for_province(province)
    if not _table_exists(table_name):
        return []

    year_candidates = ["获奖年份", "year", "年份", "年度"]
    year_col = next((c for c in year_candidates if _col_exists(table_name, c)), None)
    if not year_col:
        return []

    rows = _fetchall(
        f"SELECT `{year_col}` AS year_value FROM `{table_name}` WHERE `{year_col}` IS NOT NULL GROUP BY `{year_col}` ORDER BY `{year_col}`"
    )
    years = []
    for row in rows:
        try:
            years.append(int(row["year_value"]))
        except Exception:
            continue
    return years


QTYPE_LABELS = {
    "geo_dist": "地理位置分布",
    "discipline": "学科类型分布",
    "org_level": "学校层次分布",
    "org": "完成单位分布",
    "theme_table": "研究主题情况表",
    "completion_mode": "完成模式情况",
    "collab": "完成人员合作情况",
    "wordcloud": "研究主题词云图",
    "award_level": "获奖等级分布",
}


def qtype_label(qtype: str) -> str:
    return QTYPE_LABELS.get(qtype, qtype or "数据结果")


def split_multi_value_text(text: str) -> list[str]:
    raw = str(text or "").replace("\u3000", " ").strip()
    if not raw:
        return []
    parts = re.split(r"[、,，;；/\\|\s]+", raw)
    return [p.strip() for p in parts if p and str(p).strip()]


def split_units(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[、,，;；/\\|]+", raw)
    return [p.strip() for p in parts if p and str(p).strip()]


def collab_bucket(size: int) -> str:
    if size <= 5:
        return "1-5"
    if size <= 10:
        return "6-10"
    if size <= 15:
        return "11-15"
    return "16及以上"


def build_raw_collab_distribution(table_name: str, year: int) -> tuple[list[str], list[int], list[float]]:
    year_col = "获奖年份" if _col_exists(table_name, "获奖年份") else "year"
    cur = get_cursor()
    cur.execute(f"SELECT `完成人` FROM `{table_name}` WHERE `{year_col}`=%s", (year,))
    rows = cur.fetchall()
    cur.close()

    labels = ["1-5", "6-10", "11-15", "16及以上"]
    counts = {label: 0 for label in labels}
    total = 0
    for row in rows:
        names = split_multi_value_text(row.get("完成人"))
        if not names:
            continue
        counts[collab_bucket(len(names))] += 1
        total += 1

    values = [counts[label] for label in labels]
    pct_list = [_pct(v, total) for v in values]
    return labels, values, pct_list


def build_raw_completion_distribution(table_name: str, year: int) -> tuple[list[str], list[int], list[float]]:
    year_col = "获奖年份" if _col_exists(table_name, "获奖年份") else "year"
    cur = get_cursor()
    cur.execute(f"SELECT `完成单位` FROM `{table_name}` WHERE `{year_col}`=%s", (year,))
    rows = cur.fetchall()
    cur.close()

    labels = ["单独完成", "联合完成"]
    counts = {label: 0 for label in labels}
    total = 0
    for row in rows:
        units = split_units(row.get("完成单位"))
        if not units:
            continue
        counts["联合完成" if len(units) > 1 else "单独完成"] += 1
        total += 1

    values = [counts[label] for label in labels]
    pct_list = [_pct(v, total) for v in values]
    return labels, values, pct_list


def build_raw_collab_distribution(table_name: str, year: int, province: str | None = None) -> tuple[list[str], list[int], list[float]]:
    if table_name == MASTER_TABLE:
        year_col = "award_year"
        people_col = "authors"
        where_sql = f"WHERE `{year_col}`=%s AND `province`=%s"
        params = (year, province)
    else:
        year_col = "获奖年份" if _col_exists(table_name, "获奖年份") else "year"
        people_col = "完成人"
        where_sql = f"WHERE `{year_col}`=%s"
        params = (year,)

    cur = get_cursor()
    cur.execute(f"SELECT `{people_col}` AS people_value FROM `{table_name}` {where_sql}", params)
    rows = cur.fetchall()
    cur.close()

    labels = ["1-5", "6-10", "11-15", "16及以上"]
    counts = {label: 0 for label in labels}
    total = 0
    for row in rows:
        names = split_multi_value_text(row.get("people_value"))
        if not names:
            continue
        counts[collab_bucket(len(names))] += 1
        total += 1

    values = [counts[label] for label in labels]
    pct_list = [_pct(v, total) for v in values]
    return labels, values, pct_list


def build_raw_completion_distribution(table_name: str, year: int, province: str | None = None) -> tuple[list[str], list[int], list[float]]:
    if table_name == MASTER_TABLE:
        year_col = "award_year"
        org_col = "org_name"
        where_sql = f"WHERE `{year_col}`=%s AND `province`=%s"
        params = (year, province)
    else:
        year_col = "获奖年份" if _col_exists(table_name, "获奖年份") else "year"
        org_col = "完成单位"
        where_sql = f"WHERE `{year_col}`=%s"
        params = (year,)

    cur = get_cursor()
    cur.execute(f"SELECT `{org_col}` AS org_value FROM `{table_name}` {where_sql}", params)
    rows = cur.fetchall()
    cur.close()

    labels = ["单独完成", "联合完成"]
    counts = {label: 0 for label in labels}
    total = 0
    for row in rows:
        units = split_units(row.get("org_value"))
        if not units:
            continue
        counts["联合完成" if len(units) > 1 else "单独完成"] += 1
        total += 1

    values = [counts[label] for label in labels]
    pct_list = [_pct(v, total) for v in values]
    return labels, values, pct_list


def split_multi_value_text(text: str) -> list[str]:
    raw = str(text or "").replace("\u3000", " ").strip()
    if not raw:
        return []
    parts = re.split(r"[、,，;；/\\|\s]+", raw)
    return [p.strip() for p in parts if p and p.strip()]


def split_units(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[、,，;；/\\|\s]+", raw)
    return [p.strip() for p in parts if p and p.strip()]


def qtype_meta_for_province(province=None) -> list[dict]:
    return [
        {"value": qtype, "label": qtype_label(qtype)}
        for qtype in get_available_qtypes(province)
    ]


# =========================
# 统一分布查询（主表 count / 汇总表 sum(value_field)）
# =========================
def _query_distribution(
    year,
    group_field,
    table_name="zhejiang_awards",
    year_field="获奖年份",
    value_field=None
):
    """
    统一分布查询：
    - 主表：value_field 为 None 或 "count" -> COUNT(*)
    - 汇总表：value_field 为具体列名（如 "cnt"、"数量"） -> SUM(value_field)
    """
    if not group_field:
        raise ValueError("group_field 不能为空（请检查 qtype_specs.json 的 group_by_field）")

    if value_field == "count":
        value_field = None

    if value_field:
        sql = (
            f"SELECT `{group_field}` AS label, SUM(`{value_field}`) AS cnt "
            f"FROM `{table_name}` "
            f"WHERE `{year_field}`=%s "
            f"GROUP BY `{group_field}` "
            f"ORDER BY cnt DESC"
        )
    else:
        sql = (
            f"SELECT `{group_field}` AS label, COUNT(*) AS cnt "
            f"FROM `{table_name}` "
            f"WHERE `{year_field}`=%s "
            f"GROUP BY `{group_field}` "
            f"ORDER BY cnt DESC"
        )

    rows = _fetchall(sql, [year])
    labels = [
        ("（空）" if r["label"] is None or str(r["label"]).strip() == "" else str(r["label"]))
        for r in rows
    ]
    values = [int(r["cnt"]) for r in rows]
    return labels, values


# =========================
# ✅ 关键：把 qtype_specs.json 的“理想字段名”映射到你数据库“真实字段名”
# =========================
def _normalize_spec_for_query(spec: dict, qtype: str):
    """
    自动兼容：
    - completion_mode：award_completion_mode_summary(mode_label,cnt,pct,sort_order)
    - collab/collaboration_team：award_collab_summary(bin_label,cnt,pct,sort_order)
    """
    table_name = spec.get("table_name", "zhejiang_awards")
    year_field = spec.get("year_field", "获奖年份")
    group_field = spec.get("group_by_field")
    value_field = spec.get("value_field")

    # completion_mode
    if qtype == "completion_mode":
        if table_name == "award_completion_mode_summary":
            # 映射 group/value
            if group_field == "完成方式" and not _col_exists("award_completion_mode_summary", "完成方式"):
                if _col_exists("award_completion_mode_summary", "mode_label"):
                    group_field = "mode_label"
            if value_field == "数量" and not _col_exists("award_completion_mode_summary", "数量"):
                if _col_exists("award_completion_mode_summary", "cnt"):
                    value_field = "cnt"
            # 映射 year_field
            if year_field in ("获奖年份", None) and _col_exists("award_completion_mode_summary", "year"):
                year_field = "year"

    # collab / collaboration_team
    if qtype in ("collab", "collaboration_team"):
        if table_name == "award_collaboration_team_summary" and not _table_exists("award_collaboration_team_summary"):
            table_name = "award_collab_summary"
        if table_name == "award_collab_summary":
            if group_field in ("合作类型", None) and _col_exists("award_collab_summary", "bin_label"):
                group_field = "bin_label"
            if value_field in ("数量", None) and _col_exists("award_collab_summary", "cnt"):
                value_field = "cnt"
            if year_field in ("获奖年份", None) and _col_exists("award_collab_summary", "year"):
                year_field = "year"

    return table_name, year_field, group_field, value_field


# =========================
# /api/award-count 旧接口依赖的统计函数
# =========================
def fetch_award_count(year, dimension):
    dim_map = {
        "geo": "第一完成单位地理位置",
        "subjectType": "第一完成单位学科类型",
        "orgLevel": "第一完成单位层次",
    }
    if dimension not in dim_map:
        return None, {"error": "dimension 参数不合法"}, 400

    dim_col = dim_map[dimension]

    where_clauses = []
    params = []
    if year:
        where_clauses.append("`获奖年份` = %s")
        params.append(year)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT
            `获奖年份`,
            `{dim_col}` AS `维度`,
            COUNT(*) AS `数量`
        FROM `{TABLE}`
        {where_sql}
        GROUP BY `获奖年份`, `{dim_col}`
        ORDER BY `获奖年份`, `数量` DESC;
    """

    try:
        cursor = get_cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows, None, 200
    except Error as e:
        return None, {"error": str(e), "sql": sql}, 500


@app.route("/api/meta/options", methods=["GET"])
def api_meta_options():
    provinces = []
    for province_name, cfg in PROVINCE_CONFIG.items():
        table_name = cfg["detail_table"]
        if not has_master_data_for_province(province_name) and not _table_exists(table_name):
            continue
        years = available_years_for_province(province_name)
        provinces.append(
            {
                "value": province_name,
                "label": cfg["display_name"],
                "years": years,
                "qtypes": qtype_meta_for_province(province_name),
            }
        )

    if not provinces:
        provinces = [
            {
                "value": DEFAULT_PROVINCE,
                "label": province_display_name(DEFAULT_PROVINCE),
                "years": DEFAULT_YEARS,
                "qtypes": qtype_meta_for_province(DEFAULT_PROVINCE),
            }
        ]

    return jsonify(
        {
            "defaultProvince": DEFAULT_PROVINCE,
            "provinces": provinces,
        }
    )


@app.route("/api/material-links", methods=["GET"])
def api_material_links():
    province = normalize_province_name(request.args.get("province"))
    year = request.args.get("year", type=int)
    award_level = str(request.args.get("award_level") or "").strip()

    if not province:
        return jsonify({"error": "missing province"}), 400
    if year is None:
        return jsonify({"error": "missing year"}), 400
    if not award_level:
        return jsonify({"error": "missing award_level"}), 400

    ensure_material_links_table()

    where_parts = [
        "`province` = %s",
        "`year` = %s",
        "`is_valid` = 1",
        "`material_url` IS NOT NULL",
        "TRIM(`material_url`) <> ''",
    ]
    params = [province, year]

    if award_level != "全部":
        where_parts.append("`award_level` = %s")
        params.append(award_level)

    rows = _fetchall(
        f"""
        SELECT `award_name`, `material_url`
        FROM `{MATERIAL_LINKS_TABLE}`
        WHERE {" AND ".join(where_parts)}
        ORDER BY `award_level`, `award_name`
        """,
        params,
    )

    return jsonify(
        {
            "province": province,
            "year": year,
            "award_level": award_level,
            "total": len(rows),
            "items": [
                {
                    "award_name": row["award_name"],
                    "material_url": row["material_url"],
                }
                for row in rows
            ],
        }
    )


# =========================
# 研究主题情况表接口
# =========================
@app.route("/api/theme-table", methods=["GET"])
def api_theme_table():
    year = request.args.get("year", type=int)
    province = normalize_province_name(request.args.get("province"))
    if year is None:
        return jsonify({"error": "missing year"}), 400
    if not province_supports_qtype(province, "theme_table"):
        return jsonify({"error": f"{province_display_name(province)}暂未提供研究主题表"}), 400

    if _col_exists("award_research_theme_summary", "province"):
        sql = """
        SELECT level_name, category, item, award_count, pct
        FROM award_research_theme_summary
        WHERE year = %s AND province = %s
        ORDER BY sort_order ASC
        """
        params = (year, province)
    else:
        sql = """
        SELECT level_name, category, item, award_count, pct
        FROM award_research_theme_summary
        WHERE year = %s
        ORDER BY sort_order ASC
        """
        params = (year,)
    rows = _fetchall(sql, params)

    return jsonify(
        {
            "columns": ["层次", "类别", "条目", "奖数", "占比(%)", "_isSubtotal", "_isTotal"],
            "rows": [
                {
                    "层次": r["level_name"],
                    "类别": r["category"] or "",
                    "条目": r["item"],
                    "奖数": r["award_count"],
                    "占比(%)": float(r["pct"]),
                    "_isSubtotal": (r["item"] == "小计"),
                    "_isTotal": ("合计" in r["item"]) or (r["level_name"] == "合计"),
                }
                for r in rows
            ],
        }
    )


def fetch_theme_table_rows(year: int, province: str = DEFAULT_PROVINCE):
    if _col_exists("award_research_theme_summary", "province"):
        sql = """
        SELECT level_name, category, item, award_count, pct
        FROM award_research_theme_summary
        WHERE year = %s AND province = %s
        ORDER BY sort_order ASC
        """
        return _fetchall(sql, [year, province])
    sql = """
    SELECT level_name, category, item, award_count, pct
    FROM award_research_theme_summary
    WHERE year = %s
    ORDER BY sort_order ASC
    """
    return _fetchall(sql, [year])


def build_theme_table_summary(year: int, top_n: int = 5):
    rows = fetch_theme_table_rows(year)
    if not rows:
        return f"浙江{year}年教学成果奖获奖成果研究主题情况表：暂无可用数据。"

    detail_rows = []
    level_totals = {}
    category_totals = {}

    for row in rows:
      level = str(row.get("level_name") or "").strip()
      category = str(row.get("category") or "").strip()
      item = str(row.get("item") or "").strip()
      award_count = int(row.get("award_count") or 0)
      pct = float(row.get("pct") or 0)

      if not item or item == "小计" or "合计" in item or level == "合计":
          continue

      detail_rows.append(
          {
              "level": level,
              "category": category,
              "item": item,
              "award_count": award_count,
              "pct": pct,
          }
      )
      if level:
          level_totals[level] = level_totals.get(level, 0) + award_count
      if category:
          category_totals[category] = category_totals.get(category, 0) + award_count

    if not detail_rows:
        return f"浙江{year}年教学成果奖获奖成果研究主题情况表：仅检测到汇总行，缺少可直接分析的主题条目。"

    sorted_items = sorted(detail_rows, key=lambda x: (-x["award_count"], -x["pct"], x["item"]))
    top_items = sorted_items[: max(1, top_n)]
    top_levels = sorted(level_totals.items(), key=lambda x: (-x[1], x[0]))[:3]
    top_categories = sorted(category_totals.items(), key=lambda x: (-x[1], x[0]))[:3]

    lines = [
        f"浙江{year}年教学成果奖获奖成果研究主题情况表。",
        f"可识别的具体研究主题条目共 {len(detail_rows)} 个。",
        "高频主题：" + "；".join(
            f"{row['item']} {row['award_count']}项（{row['pct']:.2f}%）" for row in top_items
        ),
    ]

    if top_categories:
        lines.append(
            "热点类别：" + "；".join(f"{name} {count}项" for name, count in top_categories)
        )

    if top_levels:
        lines.append(
            "层次分布：" + "；".join(f"{name} {count}项" for name, count in top_levels)
        )

    return "\n".join(lines)


def build_theme_table_summary_for_province(year: int, province: str = DEFAULT_PROVINCE, top_n: int = 5):
    if province != DEFAULT_PROVINCE and not province_supports_qtype(province, "theme_table"):
        return f"{province_display_name(province)}暂未提供研究主题表。"

    rows = fetch_theme_table_rows(year, province=province)
    province_title = province_title_prefix(province)
    if not rows:
        return f"{province_title}{year}年教学成果奖研究主题情况表：暂无可用数据。"

    detail_rows = []
    level_totals = {}
    category_totals = {}

    for row in rows:
        level = str(row.get("level_name") or "").strip()
        category = str(row.get("category") or "").strip()
        item = str(row.get("item") or "").strip()
        award_count = int(row.get("award_count") or 0)
        pct = float(row.get("pct") or 0)

        if not item or item == "小计" or "合计" in item or level == "合计":
            continue

        detail_rows.append(
            {
                "level": level,
                "category": category,
                "item": item,
                "award_count": award_count,
                "pct": pct,
            }
        )
        if level:
            level_totals[level] = level_totals.get(level, 0) + award_count
        if category:
            category_totals[category] = category_totals.get(category, 0) + award_count

    if not detail_rows:
        return f"{province_title}{year}年教学成果奖研究主题情况表：仅检测到汇总行，缺少可直接分析的主题条目。"

    sorted_items = sorted(detail_rows, key=lambda x: (-x["award_count"], -x["pct"], x["item"]))
    top_items = sorted_items[: max(1, top_n)]
    top_levels = sorted(level_totals.items(), key=lambda x: (-x[1], x[0]))[:3]
    top_categories = sorted(category_totals.items(), key=lambda x: (-x[1], x[0]))[:3]

    lines = [
        f"{province_title}{year}年教学成果奖研究主题情况表。",
        f"可识别的具体研究主题条目共 {len(detail_rows)} 个。",
        "高频主题：" + "；".join(
            f"{row['item']} {row['award_count']}项（{row['pct']:.2f}%）" for row in top_items
        ),
    ]

    if top_categories:
        lines.append("热点类别：" + "；".join(f"{name} {count}项" for name, count in top_categories))

    if top_levels:
        lines.append("层次分布：" + "；".join(f"{name} {count}项" for name, count in top_levels))

    return "\n".join(lines)


def pick_first_existing(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def pick_search_fields(cols):
    candidates = ["成果名称", "项目名称", "第一完成单位", "第一完成人", "完成人", "单位", "学校名称"]
    return [c for c in candidates if c in cols]


def detect_columns(db_conn):
    schema_name = db_conn.database
    cols, types = get_table_columns(db_conn, TABLE, schema_name)

    year_col = pick_first_existing(
        cols,
        ["获奖年份", "年度", "年份", "获奖年度", "届次", "评选年度", "申报年度"],
    )

    qtype_candidates = {
        "discipline": ["第一完成单位学科类型", "学科类型", "学科门类", "学科"],
        "org_level": ["第一完成单位层次", "学校层次", "单位层次", "层次", "办学层次"],
        "org": ["第一完成单位", "完成单位", "单位名称", "学校名称"],
        "geo_dist": ["第一完成单位地理位置", "第一完成单位所在地", "所在地", "地区", "市", "地市", "地理位置"],
        "award_level": ["获奖等级", "奖励等级", "奖项等级", "等级"],
    }

    qtype_to_col = {}
    for qtype, cand_list in qtype_candidates.items():
        col = pick_first_existing(cols, cand_list)
        if col:
            qtype_to_col[qtype] = col

    return cols, types, year_col, qtype_to_col


def detect_columns_for_table(db_conn, table_name: str):
    schema_name = db_conn.database
    cols, types = get_table_columns(db_conn, table_name, schema_name)

    year_col = pick_first_existing(
        cols,
        ["获奖年份", "年度", "年份", "获奖年度", "year"],
    )

    qtype_candidates = {
        "discipline": ["第一完成单位学科类型", "学科类型", "学科门类", "学科"],
        "org_level": ["第一完成单位层次", "学校层次", "单位层次", "层次", "办学层次"],
        "org": ["第一完成单位", "完成单位", "单位名称", "学校名称", "申报单位"],
        "geo_dist": ["第一完成单位地理位置", "第一完成单位所在地", "所在地", "地区", "市", "地市", "地理位置"],
        "award_level": ["获奖等级", "建议等级", "奖励等级", "奖项等级", "等级"],
    }

    qtype_to_col = {}
    for qtype, cand_list in qtype_candidates.items():
        col = pick_first_existing(cols, cand_list)
        if col:
            qtype_to_col[qtype] = col

    return cols, types, year_col, qtype_to_col


def pick_default_year(province: str) -> int:
    years = available_years_for_province(province)
    if years:
        return years[-1]
    return DEFAULT_YEARS[-1]


def fetch_distribution_v2(province: str, year: int, qtype: str, keyword: str = "") -> dict:
    table_name = detail_table_for_province(province)
    province_title = province_title_prefix(province)
    cols, _types, year_col, qtype_to_col = detect_columns_for_table(db, table_name)
    if not year_col:
        raise ValueError(f"{province_display_name(province)}数据表缺少年份字段")

    if qtype in ("collab", "collaboration_team"):
        if province == DEFAULT_PROVINCE and _table_exists("award_collab_summary"):
            rows = _fetchall(
                "SELECT bin_label, cnt, pct FROM award_collab_summary WHERE year=%s ORDER BY sort_order",
                [year],
            )
            labels = [r["bin_label"] for r in rows]
            values = [int(r["cnt"]) for r in rows]
            pct_list = [float(r["pct"]) for r in rows]
        else:
            labels, values, pct_list = build_raw_collab_distribution(table_name, year, canonical_province if table_name == MASTER_TABLE else None)
        return {
            "type": "collab",
            "title": f"{province_title}{year}年教学成果奖完成人员合作情况",
            "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
            "meta": {"pct": pct_list},
        }

    if qtype == "completion_mode":
        if province == DEFAULT_PROVINCE and _table_exists("award_completion_mode_summary"):
            rows = _fetchall(
                """
                SELECT mode_label, cnt, pct
                FROM award_completion_mode_summary
                WHERE year=%s
                ORDER BY sort_order
                """,
                [year],
            )
            labels = [r["mode_label"] for r in rows]
            values = [int(r["cnt"]) for r in rows]
            pct_list = [float(r["pct"]) for r in rows]
        else:
            labels, values, pct_list = build_raw_completion_distribution(table_name, year, canonical_province if table_name == MASTER_TABLE else None)
        return {
            "type": "completion_mode",
            "title": f"{province_title}{year}年教学成果奖完成模式情况",
            "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
            "meta": {"pct": pct_list},
        }

    if qtype == "theme_table":
        if not province_supports_qtype(province, "theme_table"):
            raise ValueError(f"{province_display_name(province)}暂未提供研究主题表")
        rows = fetch_theme_table_rows(year, province=province)
        return {
            "columns": ["层次", "类别", "条目", "奖数", "占比(%)", "_isSubtotal", "_isTotal"],
            "rows": [
                {
                    "层次": r["level_name"],
                    "类别": r["category"] or "",
                    "条目": r["item"],
                    "奖数": r["award_count"],
                    "占比(%)": float(r["pct"]),
                    "_isSubtotal": (r["item"] == "小计"),
                    "_isTotal": ("合计" in r["item"]) or (r["level_name"] == "合计"),
                }
                for r in rows
            ],
        }

    group_col = qtype_to_col.get(qtype)
    if not group_col:
        raise ValueError(f"{province_display_name(province)}暂不支持 {qtype_label(qtype)}")

    search_fields = pick_search_fields(cols)
    if group_col not in search_fields:
        search_fields.append(group_col)

    where_sql = f"WHERE CAST(`{year_col}` AS CHAR) LIKE %s"
    params = [f"%{year}%"]
    if keyword:
        like_parts = [f"`{f}` LIKE %s" for f in search_fields]
        params.extend([f"%{keyword}%"] * len(search_fields))
        where_sql += " AND (" + " OR ".join(like_parts) + ")"

    sql = f"""
        SELECT
          COALESCE(NULLIF(TRIM(`{group_col}`), ''), '未分类') AS label,
          COUNT(*) AS value
        FROM `{table_name}`
        {where_sql}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 50
    """
    rows = _fetchall(sql, params)
    labels = [r["label"] for r in rows]
    values = [int(r["value"]) for r in rows]
    return {
        "type": qtype,
        "title": f"{province_title}{year}年{qtype_label(qtype)}",
        "chart": {"labels": labels, "datasets": [{"label": "数量", "data": values}]},
        "debug": {"year_col": year_col, "group_col": group_col, "table_name": table_name, "province": province},
    }


def detect_columns_for_table(db_conn, table_name: str):
    schema_name = db_conn.database
    cols, types = get_table_columns(db_conn, table_name, schema_name)

    year_col = pick_first_existing(
        cols,
        ["award_year", "获奖年份", "年度", "年份", "获奖年度", "year"],
    )

    qtype_candidates = {
        "discipline": ["first_org_type", "第一完成单位学科类型", "学科类型", "学科门类", "学科"],
        "org_level": ["first_org_level", "第一完成单位层次", "学校层次", "单位层次", "层次", "办学层次"],
        "org": ["org_name", "第一完成单位", "完成单位", "单位名称", "学校名称", "申报单位"],
        "geo_dist": ["first_org_location", "第一完成单位地理位置", "第一完成单位所在地", "所在地", "地区", "市", "地市", "地理位置"],
        "award_level": ["award_level", "获奖等级", "建议等级", "奖励等级", "奖项等级", "等级"],
    }

    qtype_to_col = {}
    for qtype, cand_list in qtype_candidates.items():
        col = pick_first_existing(cols, cand_list)
        if col:
            qtype_to_col[qtype] = col

    return cols, types, year_col, qtype_to_col


def fetch_distribution_v2(province: str, year: int, qtype: str, keyword: str = "") -> dict:
    canonical_province = normalize_province_name(province)
    table_name = MASTER_TABLE if has_master_data_for_province(canonical_province) else detail_table_for_province(canonical_province)
    province_title = province_title_prefix(province)
    cols, _types, year_col, qtype_to_col = detect_columns_for_table(db, table_name)
    if not year_col:
        raise ValueError(f"{province_display_name(province)}数据表缺少年份字段")

    if qtype in ("collab", "collaboration_team"):
        if table_name != MASTER_TABLE and province == DEFAULT_PROVINCE and _table_exists("award_collab_summary"):
            rows = _fetchall(
                "SELECT bin_label, cnt, pct FROM award_collab_summary WHERE year=%s ORDER BY sort_order",
                [year],
            )
            labels = [r["bin_label"] for r in rows]
            values = [int(r["cnt"]) for r in rows]
            pct_list = [float(r["pct"]) for r in rows]
        else:
            labels, values, pct_list = build_raw_collab_distribution(
                table_name,
                year,
                canonical_province if table_name == MASTER_TABLE else None,
            )
        return {
            "type": "collab",
            "title": f"{province_title}{year}年教学成果奖完成人员合作情况",
            "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
            "meta": {"pct": pct_list},
        }

    if qtype == "completion_mode":
        if table_name != MASTER_TABLE and province == DEFAULT_PROVINCE and _table_exists("award_completion_mode_summary"):
            rows = _fetchall(
                """
                SELECT mode_label, cnt, pct
                FROM award_completion_mode_summary
                WHERE year=%s
                ORDER BY sort_order
                """,
                [year],
            )
            labels = [r["mode_label"] for r in rows]
            values = [int(r["cnt"]) for r in rows]
            pct_list = [float(r["pct"]) for r in rows]
        else:
            labels, values, pct_list = build_raw_completion_distribution(
                table_name,
                year,
                canonical_province if table_name == MASTER_TABLE else None,
            )
        return {
            "type": "completion_mode",
            "title": f"{province_title}{year}年教学成果奖完成模式情况",
            "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
            "meta": {"pct": pct_list},
        }

    if qtype == "theme_table":
        if not province_supports_qtype(province, "theme_table"):
            raise ValueError(f"{province_display_name(province)}暂未提供研究主题表")
        rows = fetch_theme_table_rows(year, province=province)
        return {
            "columns": ["层次", "类别", "条目", "奖数", "占比(%)", "_isSubtotal", "_isTotal"],
            "rows": [
                {
                    "层次": r["level_name"],
                    "类别": r["category"] or "",
                    "条目": r["item"],
                    "奖数": r["award_count"],
                    "占比(%)": float(r["pct"]),
                    "_isSubtotal": (r["item"] == "小计"),
                    "_isTotal": ("合计" in r["item"]) or (r["level_name"] == "合计"),
                }
                for r in rows
            ],
        }

    group_col = qtype_to_col.get(qtype)
    if not group_col:
        raise ValueError(f"{province_display_name(province)}暂不支持 {qtype_label(qtype)}")

    search_fields = pick_search_fields(cols)
    if group_col not in search_fields:
        search_fields.append(group_col)

    where_parts = [f"CAST(`{year_col}` AS CHAR) LIKE %s"]
    params = [f"%{year}%"]
    if table_name == MASTER_TABLE:
        where_parts.append("`province`=%s")
        params.append(canonical_province)
    if keyword:
        like_parts = [f"`{f}` LIKE %s" for f in search_fields]
        params.extend([f"%{keyword}%"] * len(search_fields))
        where_parts.append("(" + " OR ".join(like_parts) + ")")

    sql = f"""
        SELECT
          COALESCE(NULLIF(TRIM(`{group_col}`), ''), '未分类') AS label,
          COUNT(*) AS value
        FROM `{table_name}`
        WHERE {' AND '.join(where_parts)}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 50
    """
    rows = _fetchall(sql, params)
    labels = [r["label"] for r in rows]
    values = [int(r["value"]) for r in rows]
    return {
        "type": qtype,
        "title": f"{province_title}{year}年{qtype_label(qtype)}",
        "chart": {"labels": labels, "datasets": [{"label": "数量", "data": values}]},
        "debug": {"year_col": year_col, "group_col": group_col, "table_name": table_name, "province": canonical_province},
    }


def fetch_wordcloud_row_v2(province: str, year: int):
    if not province_supports_qtype(province, "wordcloud"):
        return None
    if not _table_exists("wordcloud_images"):
        return None

    if _col_exists("wordcloud_images", "province"):
        return _fetchone(
            "SELECT mime_type, img, filename FROM wordcloud_images WHERE year=%s AND province=%s",
            [year, province],
        )
    if province != DEFAULT_PROVINCE:
        return None
    return _fetchone(
        "SELECT mime_type, img, filename FROM wordcloud_images WHERE year=%s",
        [year],
    )


def build_summary_text_v2(province: str, year: int, qtype: str, top_n: int = 5) -> str:
    if qtype == "theme_table":
        return build_theme_table_summary_for_province(year, province=province, top_n=top_n)

    if qtype == "wordcloud":
        row = fetch_wordcloud_row_v2(province, year)
        if not row:
            return f"{province_display_name(province)}{year}年词云图暂无可用数据。"
        return f"{province_title_prefix(province)}{year}年教学成果奖研究主题词云图可用。"

    data = fetch_distribution_v2(province, year, qtype)
    labels = data.get("chart", {}).get("labels", [])
    values = data.get("chart", {}).get("datasets", [{}])[0].get("data", [])
    dist = _build_dist_summary(labels, values, top_n=top_n)

    lines = [f"{data.get('title') or qtype_label(qtype)}。总计 {dist['total']} 项。"]
    for i, t in enumerate(dist["top"], start=1):
        lines.append(f"Top{i}：{t['label']} {t['count']}项（{t['percent']}%）")
    if dist["others"]["count"] > 0:
        lines.append(f"其余合计：{dist['others']['count']}项（{dist['others']['percent']}%）")
    lines.append(f"集中度（Top1占比）：{dist['top1_percent']}%")
    return "\n".join(lines)


# =========================
# 分布统计接口（保留你的 /api/dist 逻辑）
# =========================
@app.route("/api/dist", methods=["GET"])
def api_dist():
    year = request.args.get("year", type=int)
    qtype = request.args.get("qtype", default="discipline", type=str)
    keyword = request.args.get("keyword", default="", type=str).strip()
    province = normalize_province_name(request.args.get("province"))
    table_name = detail_table_for_province(province)
    province_title = province_title_prefix(province)

    if year is None:
        return jsonify({"error": "missing year"}), 400
    if not _table_exists(table_name):
        return jsonify({"error": f"{province_display_name(province)}数据表不存在"}), 400
    if not province_supports_qtype(province, qtype):
        return jsonify({"error": f"{province_display_name(province)}暂不支持 {qtype_label(qtype)}"}), 400

    # ✅ 完成人员合作情况（兼容 collab / collaboration_team）
    if qtype in ("collab", "collaboration_team"):
        rows = _fetchall(
            "SELECT bin_label, cnt, pct FROM award_collab_summary WHERE year=%s ORDER BY sort_order",
            (year,),
        )

        labels = [r["bin_label"] for r in rows]
        values = [int(r["cnt"]) for r in rows]
        pct_list = [float(r["pct"]) for r in rows]

        return jsonify(
            {
                "type": "collab",
                "title": f"浙江{year}年教学成果奖完成人员合作情况（完成人数分档）",
                "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
                "meta": {"pct": pct_list},
            }
        )

    # ✅ 获奖成果完成模式情况（completion_mode）
    if qtype == "completion_mode":
        rows = _fetchall(
            """
            SELECT mode_label, cnt, pct
            FROM award_completion_mode_summary
            WHERE year=%s
            ORDER BY sort_order
            """,
            (year,),
        )

        labels = [r["mode_label"] for r in rows]
        values = [int(r["cnt"]) for r in rows]
        pct_list = [float(r["pct"]) for r in rows]

        return jsonify(
            {
                "type": "completion_mode",
                "title": f"浙江{year}年教学成果奖获奖成果完成模式情况",
                "chart": {"labels": labels, "datasets": [{"label": "数量（项）", "data": values}]},
                "meta": {"pct": pct_list},
            }
        )

    # ✅ 其它 qtype：走自动识别
    cols, types, year_col, qtype_to_col = detect_columns(db)

    if not year_col:
        return jsonify(
            {
                "error": "无法自动识别年份列（YEAR_COL）",
                "hint": "请在表字段中确认哪个是年份/年度/届次列",
                "columns": cols,
            }
        ), 400

    group_col = qtype_to_col.get(qtype)
    if not group_col:
        return jsonify(
            {
                "error": f"无法自动识别该 qtype 对应列：{qtype}",
                "hint": "请确认该分布类型在表中对应哪个字段",
                "columns": cols,
                "detected_qtype_to_col": qtype_to_col,
            }
        ), 400

    search_fields = pick_search_fields(cols)
    if group_col not in search_fields:
        search_fields.append(group_col)

    where_sql = f"WHERE CAST(`{year_col}` AS CHAR) LIKE %s"
    params = [f"%{year}%"]

    if keyword:
        like_parts = [f"`{f}` LIKE %s" for f in search_fields]
        params.extend([f"%{keyword}%"] * len(search_fields))
        where_sql += " AND (" + " OR ".join(like_parts) + ")"

    sql = f"""
        SELECT
          COALESCE(NULLIF(TRIM(`{group_col}`), ''), '未分类') AS label,
          COUNT(*) AS value
        FROM `{TABLE}`
        {where_sql}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 50
    """

    rows = _fetchall(sql, params)

    labels = [r["label"] for r in rows]
    values = [int(r["value"]) for r in rows]

    return jsonify(
        {
            "type": qtype,
            "title": f"浙江{year}年{qtype}分布",
            "chart": {"labels": labels, "datasets": [{"label": "数量", "data": values}]},
            "debug": {"year_col": year_col, "group_col": group_col},
        }
    )


# =========================
# 词云图接口
# =========================
@app.route("/api/wordcloud/years", methods=["GET"])
def wordcloud_years():
    rows = _fetchall("SELECT year, filename FROM wordcloud_images ORDER BY year;")
    return jsonify(rows)


@app.route("/api/wordcloud/<int:year>", methods=["GET"])
def wordcloud_image(year):
    global db
    last_err = None
    row = None
    for _ in range(2):
        cur = None
        try:
            db.ping(reconnect=True, attempts=2, delay=0)
            cur = db.cursor()
            cur.execute("SELECT mime_type, img FROM wordcloud_images WHERE year=%s", (year,))
            row = cur.fetchone()
            break
        except Exception as e:
            last_err = e
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                db.close()
            except Exception:
                pass
            db = _connect_db()
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
    if row is None and last_err is not None:
        raise last_err

    if not row:
        return jsonify({"error": "not found"}), 404

    mime_type, img_bytes = row
    return Response(img_bytes, mimetype=mime_type)


@app.route("/api/v2/dist", methods=["GET"])
def api_dist_v2():
    year = request.args.get("year", type=int)
    qtype = request.args.get("qtype", default="discipline", type=str)
    keyword = request.args.get("keyword", default="", type=str).strip()
    province = normalize_province_name(request.args.get("province"))

    if year is None:
        return jsonify({"error": "missing year"}), 400

    try:
        return jsonify(fetch_distribution_v2(province, year, qtype, keyword))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/v2/theme-table", methods=["GET"])
def api_theme_table_v2():
    year = request.args.get("year", type=int)
    province = normalize_province_name(request.args.get("province"))
    if year is None:
        return jsonify({"error": "missing year"}), 400

    try:
        return jsonify(fetch_distribution_v2(province, year, "theme_table"))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/v2/wordcloud/years", methods=["GET"])
def wordcloud_years_v2():
    province = normalize_province_name(request.args.get("province"))
    years = available_years_for_province(province)
    rows = []
    for year in years:
        row = fetch_wordcloud_row_v2(province, year)
        if row:
            rows.append({"year": year, "filename": row.get("filename")})
    return jsonify(rows)


@app.route("/api/v2/wordcloud/<int:year>", methods=["GET"])
def wordcloud_image_v2(year):
    province = normalize_province_name(request.args.get("province"))
    row = fetch_wordcloud_row_v2(province, year)
    if not row:
        return jsonify({"error": "not found"}), 404
    return Response(row["img"], mimetype=row["mime_type"])


# =========================
# 测试接口
# =========================
@app.route("/test", methods=["GET"])
def test():
    app_file = os.path.abspath(__file__)

    cursor = get_cursor()
    cursor.execute("SELECT @@hostname AS host, @@port AS port, @@server_uuid AS uuid, @@version AS ver, USER() AS user")
    server = cursor.fetchone()

    cursor.execute("SELECT DATABASE() AS current_db;")
    current_db = cursor.fetchone()["current_db"]

    cursor.execute(f"SELECT COUNT(*) AS total_rows FROM `{TABLE}`;")
    total_rows = cursor.fetchone()["total_rows"]

    cursor.close()

    routes = sorted([str(r) for r in app.url_map.iter_rules()])

    return jsonify(
        {
            "app_file": app_file,
            "current_db": current_db,
            "mysql_server": server,
            "total_rows": total_rows,
            "routes": routes,
        }
    )


# =========================
# 旧接口：/api/award-count
# =========================
@app.route("/api/award-count", methods=["GET"])
def award_count():
    year = request.args.get("year")
    dimension = request.args.get("dimension", "geo")

    rows, err, code = fetch_award_count(year, dimension)
    if err:
        return jsonify(err), code
    return jsonify(rows)


# =========================
# ✅ 生成摘要接口：基于 qtype_specs.json + 自动兼容映射
# =========================
@app.route("/api/summary", methods=["GET"])
def api_summary():
    specs = load_qtype_specs()

    year = request.args.get("year", type=int)
    qtype = request.args.get("qtype", type=str)
    top_n = request.args.get("top_n", default=5, type=int)

    if not year or not qtype:
        return jsonify({"error": "缺少 year 或 qtype 参数"}), 400
    if qtype not in specs:
        return jsonify({"error": f"未知 qtype: {qtype}"}), 400

    spec = specs[qtype]
    kind = spec.get("kind")
    title_tpl = spec.get("title_template") or ""
    title = title_tpl.replace("{year}", str(year)) if title_tpl else f"{qtype}（{year}）"

    # 图片类
    if kind == "image":
        url_tpl = spec.get("url_template", "")
        url = url_tpl.replace("{year}", str(year))
        return jsonify({
            "kind": "image",
            "year": year,
            "qtype": qtype,
            "title": title,
            "image": {"url": url},
            "summary_text": f"{title}：图片资源可通过 {url} 获取。"
        })

    # 表格类
    if kind == "table":
        table_name = spec.get("table_name")
        if not table_name:
            return jsonify({"error": "qtype_specs.json 未配置 table_name"}), 500
        year_field = spec.get("year_field", "year")
        row = _fetchone(f"SELECT COUNT(*) AS cnt FROM `{table_name}` WHERE `{year_field}`=%s", [year])
        cnt = int(row["cnt"]) if row else 0
        return jsonify({
            "kind": "table",
            "year": year,
            "qtype": qtype,
            "title": title,
            "table": {"row_count": cnt},
            "summary_text": f"{title}：共 {cnt} 行。"
        })

    # 图表类
    if kind == "chart":
        table_name, year_field, group_field, value_field = _normalize_spec_for_query(spec, qtype)
        if not group_field:
            return jsonify({"error": "qtype_specs.json 未配置 group_by_field"}), 500

        labels, values = _query_distribution(
            year,
            group_field,
            table_name=table_name,
            year_field=year_field,
            value_field=value_field
        )
        dist = _build_dist_summary(labels, values, top_n=top_n)

        lines = [f"{title}。总计 {dist['total']} 条。"]
        for i, t in enumerate(dist["top"], start=1):
            lines.append(f"Top{i}：{t['label']} {t['count']}（{t['percent']}%）")
        if dist["others"]["count"] > 0:
            lines.append(f"其余合计：{dist['others']['count']}（{dist['others']['percent']}%）")
        lines.append(f"集中度（Top1占比）：{dist['top1_percent']}%")

        return jsonify({
            "kind": "chart",
            "year": year,
            "qtype": qtype,
            "title": title,
            "distribution": dist,
            "summary_text": "\n".join(lines),
            "debug": {
                "table_name": table_name,
                "year_field": year_field,
                "group_field": group_field,
                "value_field": value_field
            }
        })

    return jsonify({"error": f"不支持的 kind: {kind}"}), 500


# =========================
# ✅ 意图识别：从问题推断 qtype / 年份 / 是否对比
# =========================
QTYPE_ALIAS = {
    "geo_dist": ["地理位置", "地区", "地市", "城市", "所在地", "地理分布", "地理位置分布"],
    "discipline": ["学科", "学科类型", "学科分布"],
    "org_level": ["学校层次", "单位层次", "层次"],
    "completion_mode": ["完成模式", "完成方式", "合作模式"],
    "collab": ["完成人员合作", "合作情况", "完成人数", "分档"],
    "theme_table": ["研究主题", "主题情况表"],
    "wordcloud": ["词云", "词云图"],
}


def normalize_query_contexts(raw_contexts):
    if not isinstance(raw_contexts, list):
        return []

    contexts = []
    for item in raw_contexts[:5]:
        if not isinstance(item, dict):
            continue

        qtype = str(item.get("qtype") or "").strip()
        if not qtype:
            continue

        year = item.get("year")
        try:
            year = int(year) if year not in (None, "") else None
        except Exception:
            year = None

        searched_at = item.get("searchedAt") or 0
        try:
            searched_at = int(searched_at)
        except Exception:
            searched_at = 0

        chart_summary = item.get("chartSummary")
        if isinstance(chart_summary, dict):
            labels = chart_summary.get("labels") or []
            values = chart_summary.get("values") or []
            if not isinstance(labels, list) or not isinstance(values, list):
                chart_summary = None
            else:
                chart_summary = {
                    "labels": [str(x) for x in labels[:80]],
                    "values": [float(x or 0) for x in values[:80]],
                }
        else:
            chart_summary = None

        contexts.append(
            {
                "qtype": qtype,
                "year": year,
                "keyword": str(item.get("keyword") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "view": str(item.get("view") or "").strip(),
                "searchedAt": searched_at,
                "province": normalize_province_name(item.get("province")),
                "compareActive": bool(item.get("compareActive")),
                "compareSide": str(item.get("compareSide") or "").strip(),
                "compareTitle": str(item.get("compareTitle") or "").strip(),
                "chartSummary": chart_summary,
            }
        )

    contexts.sort(key=lambda x: x.get("searchedAt", 0), reverse=True)
    return contexts


def normalize_query_contexts_v2(raw_contexts):
    contexts = normalize_query_contexts(raw_contexts)
    for ctx in contexts:
        ctx["province"] = normalize_province_name(ctx.get("province"))
    contexts.sort(key=lambda x: x.get("searchedAt", 0), reverse=True)
    return contexts


def infer_province(question: str, query_contexts=None) -> str:
    query_contexts = query_contexts or []
    q = str(question or "").strip()
    for alias, canonical in PROVINCE_ALIASES.items():
        if alias and alias in q:
            return canonical
    if query_contexts:
        latest = query_contexts[0]
        if latest.get("province"):
            return normalize_province_name(latest["province"])
    return DEFAULT_PROVINCE


CHINA_REGION_NAMES = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "海南省",
    "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省",
    "台湾省", "内蒙古自治区", "广西壮族自治区", "西藏自治区",
    "宁夏回族自治区", "新疆维吾尔自治区", "香港特别行政区", "澳门特别行政区",
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
]


def extract_region_mention(question: str) -> str | None:
    q = str(question or "").strip()
    if not q:
        return None
    for name in sorted(CHINA_REGION_NAMES, key=len, reverse=True):
        if name in q:
            return name
    return None


def province_has_platform_data(province: str) -> bool:
    return normalize_province_name(province) in PROVINCE_CONFIG


def build_summary_from_chart_context(ctx: dict, top_n: int = 5) -> str | None:
    chart_summary = ctx.get("chartSummary")
    if not isinstance(chart_summary, dict):
        return None
    labels = chart_summary.get("labels") or []
    values = chart_summary.get("values") or []
    if not labels or not values:
        return None
    dist = _build_dist_summary(labels, values, top_n=top_n)
    province = province_display_name(ctx.get("province"))
    year = ctx.get("year") or ""
    qtype = qtype_label(ctx.get("qtype") or "")
    title = ctx.get("title") or f"{province}{year}年{qtype}"
    lines = [f"{title}。总计 {dist['total']} 项。"]
    for i, t in enumerate(dist["top"], start=1):
        lines.append(f"Top{i}：{t['label']} {t['count']}项（{t['percent']}%）")
    if dist["others"]["count"] > 0:
        lines.append(f"其余合计：{dist['others']['count']}项（{dist['others']['percent']}%）")
    lines.append(f"集中度（Top1占比）：{dist['top1_percent']}%")
    lines.append("来源：当前页面对比图表数据。")
    return "\n".join(lines)


def build_context_block(query_contexts):
    if not query_contexts:
        return ""

    lines = ["【当前查询上下文】"]
    for idx, ctx in enumerate(query_contexts[:3], start=1):
        parts = [f"最近查询{idx}"]
        if ctx.get("title"):
            parts.append(ctx["title"])
        else:
            parts.append(ctx.get("qtype") or "未命名查询")
        if ctx.get("year"):
            parts.append(f"年份={ctx['year']}")
        if ctx.get("view"):
            parts.append(f"视图={ctx['view']}")
        if ctx.get("keyword"):
            parts.append(f"关键词={ctx['keyword']}")
        lines.append("，".join(parts))
    return "\n".join(lines)


def apply_query_context_to_intent(question: str, intent: dict, query_contexts):
    if not query_contexts:
        return intent

    q = (question or "").strip()
    latest = query_contexts[0]
    refer_recent_keywords = [
        "刚刚查询", "刚刚查", "刚才查询", "刚才查",
        "我查询的", "我刚刚查询的", "当前查询", "当前结果",
        "这张表", "这个结果", "该表", "该结果",
    ]
    refers_recent = any(k in q for k in refer_recent_keywords)

    if refers_recent and latest.get("qtype"):
        intent["qtype"] = latest["qtype"]
        if not intent.get("is_compare") and latest.get("year"):
            intent["year"] = latest["year"]
        return intent

    if not intent.get("qtype") and latest.get("qtype"):
        intent["qtype"] = latest["qtype"]
    if not intent.get("is_compare") and not intent.get("year") and latest.get("year"):
        intent["year"] = latest["year"]
    return intent

def infer_intent(question: str):
    q = (question or "").strip()

    # 1) 提取年份
    years = re.findall(r"(20\d{2})", q)
    years = [int(y) for y in years]

    # 2) 判断是否属于“变化/趋势/对比”类问题
    compare_keywords = [
        "对比", "比较", "相比",
        "上升", "下降", "提高", "降低",
        "变高", "变低", "增长", "减少",
        "变化", "趋势", "波动",
        "提升", "下滑", "走高", "走低",
        "排名上升", "排名下降", "名次上升", "名次下降",
        "遥遥领先", "领先", "落后", "赶超"
    ]
    is_compare = any(k in q for k in compare_keywords) or (len(set(years)) >= 2)

    # 3) 判断 qtype
    qtype = None

    # 先按配置别名匹配
    for k, kws in QTYPE_ALIAS.items():
        if any(kw in q for kw in kws):
            qtype = k
            break

    # 额外补充：如果问题里出现城市名/地域排名，也默认视为 geo_dist
    city_keywords = [
        "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴",
        "金华", "衢州", "舟山", "台州", "丽水"
    ]
    geo_ranking_keywords = ["排名", "城市", "地区", "地市", "地域", "所在地"]

    if qtype is None:
        if any(k in q for k in city_keywords) or any(k in q for k in geo_ranking_keywords):
            qtype = "geo_dist"

    # 4) 年份策略
    year = years[0] if years else None
    y1, y2 = None, None

    if is_compare:
        uniq = sorted(list(set(years)))
        if len(uniq) >= 2:
            y1, y2 = uniq[0], uniq[1]
        elif len(uniq) == 1:
            # 只写了一个年份时，自动补一个对比基准年
            if uniq[0] == 2025:
                y1, y2 = 2021, 2025
            else:
                y1, y2 = uniq[0], 2025
        else:
            # 没写年份，但问法明显是趋势/变化类，默认比较 2021 vs 2025
            y1, y2 = 2021, 2025

    return {
        "is_compare": is_compare,
        "qtype": qtype,
        "year": year,
        "y1": y1,
        "y2": y2,
    }

def decide_answer_mode(question: str, intent: dict, query_contexts=None):
    q = (question or "").strip()
    query_contexts = query_contexts or []

    reasoning_keywords = [
        "为什么", "为何", "原因", "成因", "背后", "怎么解释", "解释一下",
        "意味着什么", "说明什么", "启示", "建议", "怎么看", "如何看待",
        "趋势", "影响因素", "优势", "劣势", "问题在哪", "为什么会这样"
    ]

    creative_keywords = [
        "标题", "题目", "命名", "名称", "推荐", "建议", "拟题", "选题",
        "方向", "摘要", "提纲", "亮点", "关键词", "写作", "申报",
        "方案", "优化", "润色", "设计"
    ]

    data_keywords = [
        "分布", "占比", "top", "TOP", "排名", "数量", "多少", "对比", "比较",
        "变化", "增长", "下降", "学科", "地理位置", "学校层次", "身份",
        "合作情况", "完成模式", "研究主题", "词云"
    ]

    # infer_intent 已经识别出 qtype / compare / year，就说明大概率和平台数据有关
    has_data_signal = (
        bool(intent.get("qtype")) or
        bool(intent.get("is_compare")) or
        any(k in q for k in data_keywords)
    )

    has_reasoning_signal = any(k in q for k in reasoning_keywords)
    has_creative_signal = any(k in q for k in creative_keywords)

    if has_creative_signal and (has_data_signal or bool(query_contexts)):
        return "contextual_general"

    if has_data_signal and has_reasoning_signal:
        return "data_plus_reasoning"

    if has_data_signal:
        return "data_only"

    return "general"

def build_chat_messages(question: str, session_id: str, answer_mode: str, summary_block: str, context_block: str):
    history = CHAT_SESSIONS.get(session_id, [])
    context_hint = (
        f"{context_block}\n\n"
        "如果当前查询上下文与历史对话不一致，请优先以当前查询上下文为准。\n\n"
    ) if context_block else ""

    if answer_mode == "data_only":
        system_prompt = (
            "你是一个中文数据分析助手，负责解读“浙江省教学成果奖平台”的数据库结果。\n"
            "请严格基于给定的数据摘要回答，不要编造数据库中没有出现的具体数值。\n"
            "回答要求：\n"
            "1. 先给结论，再给依据。\n"
            "2. 如果问题是对比类，明确说明变化点。\n"
            "3. 如果摘要不足以支持结论，明确说“当前数据不足以判断”。"
        )
        user_content = f"{context_hint}{summary_block}\n\n【用户问题】\n{question}"

    elif answer_mode == "data_plus_reasoning":
        system_prompt = (
            "你是一个中文教育数据分析助手。\n"
            "你会收到平台数据库生成的数据摘要，但你的回答不应局限于机械复述。\n"
            "回答时请分两层：\n"
            "第一层【数据可直接支持】：只陈述摘要中能直接看出的事实；\n"
            "第二层【结合领域经验的解释/推断】：可以结合一般教育管理、区域高教资源、产教融合、科研基础、政策支持等常识做合理解释。\n"
            "注意：\n"
            "1. 不要把“推断”说成“数据库已证明”；\n"
            "2. 对推断性内容，要用“可能”“通常”“从一般经验看”等表述；\n"
            "3. 如果问题部分超出数据库覆盖范围，也可以正常作答，但要分清“数据事实”和“推断解释”。"
        )
        user_content = f"{context_hint}{summary_block}\n\n【用户问题】\n{question}"

    elif answer_mode == "contextual_general":
        system_prompt = (
            "你是一个中文教育分析与写作助手，同时熟悉教学成果奖、高等教育治理、成果申报与学术表达。\n"
            "你会收到平台数据库的当前查询上下文和相关数据摘要。\n"
            "回答原则：\n"
            "1. 涉及平台事实时，只能依据提供的数据摘要；\n"
            "2. 涉及标题推荐、命名、写作建议、选题设计、表达优化等创造性任务时，可以结合当前数据线索和你自己的分析能力正常回答；\n"
            "3. 如果数据线索只提供方向、不足以支持具体事实判断，应明确说明“以下建议是结合当前主题线索与一般经验生成”；\n"
            "4. 如果当前查询上下文与历史对话冲突，以当前查询上下文为准。"
        )
        user_content = f"{context_hint}{summary_block}\n\n【用户问题】\n{question}"

    else:  # general
        system_prompt = (
            "你是一个中文通用智能助手，同时熟悉教学成果奖、教育评估、申报写作和高等教育治理等话题。\n"
            "当用户问题不依赖平台数据库时，直接正常回答即可。\n"
            "回答应清晰、自然、有条理，不要强行提及数据库。"
        )
        user_content = question

    messages = [{"role": "system", "content": system_prompt}]

    for h in history[-10:]:
        if h["role"] in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_content})
    return messages


# =========================
# ✅ 会话工具
# =========================
def _now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _get_or_create_session(session_id: str | None):
    if session_id and session_id in CHAT_SESSIONS:
        return session_id
    new_id = uuid.uuid4().hex
    CHAT_SESSIONS[new_id] = []
    return new_id

def _append_session(session_id: str, role: str, content: str):
    CHAT_SESSIONS.setdefault(session_id, [])
    CHAT_SESSIONS[session_id].append({"role": role, "content": content, "ts": _now_ts()})
    # 简单裁剪，避免无限长
    if len(CHAT_SESSIONS[session_id]) > 30:
        CHAT_SESSIONS[session_id] = CHAT_SESSIONS[session_id][-30:]


# =========================
# ✅ /chat/clear：清空会话
# =========================
@app.route("/chat/clear", methods=["POST"])
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    session_id = (body.get("session_id") or "").strip()
    query_contexts = normalize_query_contexts(body.get("query_contexts") or [])
    question = (body.get("question") or "").strip()
    top_n = int(body.get("top_n", 5))

    if request.path.endswith("/chat/clear"):
        if session_id:
            CHAT_SESSIONS.pop(session_id, None)
            CHAT_CONTEXTS.pop(session_id, None)
        return jsonify({"ok": True, "session_id": session_id})

    if not question:
        return jsonify({"error": "question 不能为空"}), 400

    # 1) session
    session_id = _get_or_create_session(session_id)
    if query_contexts:
        CHAT_CONTEXTS[session_id] = query_contexts
    else:
        query_contexts = CHAT_CONTEXTS.get(session_id, [])

    # 2) 推断意图
    intent = infer_intent(question)
    intent = apply_query_context_to_intent(question, intent, query_contexts)
    qtype = intent["qtype"]
    answer_mode = decide_answer_mode(question, intent, query_contexts)
    context_block = build_context_block(query_contexts)

    # 3) 年份策略
    if intent["is_compare"]:
        y1 = intent["y1"] or 2021
        y2 = intent["y2"] or 2025
        years = [y1, y2]
    else:
        years = [intent["year"] or 2025]

    # 4) 生成摘要（数据问答与带上下文的创意问答都需要）
    summaries = []

    if answer_mode in ("data_only", "data_plus_reasoning", "contextual_general"):
        try:
            specs = load_qtype_specs()
            if qtype not in specs:
                qtype = query_contexts[0]["qtype"] if query_contexts else "geo_dist"

            for y in years:
                spec = specs[qtype]
                kind = spec.get("kind")

                title_tpl = spec.get("title_template") or ""
                title = title_tpl.replace("{year}", str(y)) if title_tpl else f"{qtype}（{y}）"

                if kind == "chart":
                    table_name, year_field, group_field, value_field = _normalize_spec_for_query(spec, qtype)
                    labels, values = _query_distribution(
                        int(y),
                        group_field,
                        table_name=table_name,
                        year_field=year_field,
                        value_field=value_field
                    )
                    dist = _build_dist_summary(labels, values, top_n=top_n)
                    lines = [f"{title}。总计 {dist['total']} 条。"]
                    for i, t in enumerate(dist["top"], start=1):
                        lines.append(f"Top{i}：{t['label']} {t['count']}（{t['percent']}%）")
                    if dist["others"]["count"] > 0:
                        lines.append(f"其余合计：{dist['others']['count']}（{dist['others']['percent']}%）")
                    lines.append(f"集中度（Top1占比）：{dist['top1_percent']}%")
                    summaries.append("\n".join(lines))

                elif kind == "table":
                    if qtype == "theme_table":
                        summaries.append(build_theme_table_summary(int(y), top_n=top_n))
                    else:
                        table_name = spec.get("table_name")
                        year_field = spec.get("year_field", "year")
                        row = _fetchone(f"SELECT COUNT(*) AS cnt FROM `{table_name}` WHERE `{year_field}`=%s", [y])
                        cnt = int(row["cnt"]) if row else 0
                        summaries.append(f"{title}：共 {cnt} 行。")

                elif kind == "image":
                    url_tpl = spec.get("url_template", "")
                    url = url_tpl.replace("{year}", str(y))
                    summaries.append(f"{title}：图片资源可通过 {url} 获取。")

                else:
                    summaries.append(f"{title}：暂不支持该类型摘要。")

        except Exception as e:
            return jsonify({"error": f"生成摘要失败：{str(e)}"}), 500

    # 5) 拼装给模型的上下文
    if answer_mode == "general":
        summary_block = ""
    elif len(summaries) == 1:
        summary_block = f"【数据摘要】\n{summaries[0]}"
    else:
        summary_block = "【数据摘要-多年份】\n" + "\n\n---\n\n".join(summaries)


    # 6) 组装 messages（带会话历史）
    messages = build_chat_messages(question, session_id, answer_mode, summary_block, context_block)

    _append_session(session_id, "user", question)

    @stream_with_context
    def generate():
        full_answer = ""

        # 告诉前端 session_id
        yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id}, ensure_ascii=False)}\n\n"

        # 告诉前端开始思考
        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"

        try:
            for chunk in deepseek_chat_stream(messages):
                if not chunk:
                    continue
                full_answer += chunk
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk}, ensure_ascii=False)}\n\n"
                time.sleep(0.012)

            full_answer = full_answer.strip() or "（无回答）"
            _append_session(session_id, "assistant", full_answer)

            yield f"data: {json.dumps({'type': 'done', 'answer': full_answer}, ensure_ascii=False)}\n\n"

        except Exception as e:
            err_text = f"调用 DeepSeek 失败：{str(e)}"
            _append_session(session_id, "assistant", err_text)
            yield f"data: {json.dumps({'type': 'error', 'error': err_text}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/chat/v2", methods=["POST"])
def chat_v2():
    body = request.get_json(silent=True) or {}
    session_id = (body.get("session_id") or "").strip()
    query_contexts = normalize_query_contexts_v2(body.get("query_contexts") or [])
    compare_context = body.get("compare_context") or {}
    explicit_compare_contexts = []
    if isinstance(compare_context, dict) and compare_context.get("active"):
        explicit_compare_contexts = normalize_query_contexts_v2(compare_context.get("items") or [])
        for ctx in explicit_compare_contexts:
            ctx["compareActive"] = True
            if compare_context.get("title") and not ctx.get("compareTitle"):
                ctx["compareTitle"] = str(compare_context.get("title") or "").strip()
    if len(explicit_compare_contexts) >= 2:
        query_contexts = explicit_compare_contexts + [
            ctx for ctx in query_contexts if not ctx.get("compareActive")
        ]
    question = (body.get("question") or "").strip()
    top_n = int(body.get("top_n", 5))

    if not question:
        return jsonify({"error": "question 不能为空"}), 400

    session_id = _get_or_create_session(session_id)
    if query_contexts:
        CHAT_CONTEXTS[session_id] = query_contexts
    else:
        query_contexts = CHAT_CONTEXTS.get(session_id, [])

    intent = infer_intent(question)
    intent = apply_query_context_to_intent(question, intent, query_contexts)
    answer_mode = decide_answer_mode(question, intent, query_contexts)
    compare_contexts = [ctx for ctx in query_contexts if ctx.get("compareActive")]
    if len(compare_contexts) >= 2 and answer_mode == "general":
        answer_mode = "data_plus_reasoning"

    requested_region = extract_region_mention(question)
    inferred_province = infer_province(question, query_contexts)
    province = normalize_province_name(requested_region) if requested_region else inferred_province
    if len(compare_contexts) >= 2 and not requested_region:
        province = normalize_province_name(compare_contexts[0].get("province"))
    has_platform_data = province_has_platform_data(province)

    qtype = intent.get("qtype") or (query_contexts[0]["qtype"] if query_contexts else "org")
    if len(compare_contexts) >= 2 and compare_contexts[0].get("qtype"):
        qtype = compare_contexts[0]["qtype"]
    if has_platform_data and not province_supports_qtype(province, qtype):
        available = get_available_qtypes(province)
        qtype = available[0] if available else "org"

    needs_data_summary = answer_mode in ("data_only", "data_plus_reasoning")
    if answer_mode == "contextual_general" and has_platform_data:
        needs_data_summary = True

    summaries = []
    if needs_data_summary and has_platform_data:
        if len(compare_contexts) >= 2:
            ordered_contexts = sorted(compare_contexts[:2], key=lambda x: x.get("compareSide") == "right")
            for ctx in ordered_contexts:
                chart_summary_text = build_summary_from_chart_context(ctx, top_n=top_n)
                if chart_summary_text:
                    summaries.append(chart_summary_text)
                    continue

                ctx_province = normalize_province_name(ctx.get("province") or province)
                ctx_qtype = ctx.get("qtype") or qtype
                ctx_year = ctx.get("year") or pick_default_year(ctx_province)
                if not province_has_platform_data(ctx_province):
                    summaries.append(f"{province_display_name(ctx_province)}：当前平台暂无该省份结构化数据。")
                    continue
                if not province_supports_qtype(ctx_province, ctx_qtype):
                    available = get_available_qtypes(ctx_province)
                    ctx_qtype = available[0] if available else ctx_qtype
                try:
                    summaries.append(build_summary_text_v2(ctx_province, int(ctx_year), ctx_qtype, top_n=top_n))
                except Exception as e:
                    summaries.append(str(e))
        else:
            if intent.get("is_compare"):
                y1 = intent.get("y1") or pick_default_year(province)
                y2 = intent.get("y2") or pick_default_year(province)
                years = [y1, y2]
            else:
                years = [intent.get("year") or pick_default_year(province)]

            for year in years:
                try:
                    summaries.append(build_summary_text_v2(province, int(year), qtype, top_n=top_n))
                except Exception as e:
                    summaries.append(str(e))

    context_lines = []
    for idx, ctx in enumerate(query_contexts[:3], start=1):
        if ctx.get("compareActive"):
            side_label = "左侧对比项" if ctx.get("compareSide") == "left" else "右侧对比项"
            parts = [side_label]
        else:
            parts = [f"最近查询{idx}"]
        if ctx.get("province"):
            parts.append(f"省份={province_display_name(ctx['province'])}")
        if ctx.get("year"):
            parts.append(f"年份={ctx['year']}")
        if ctx.get("title"):
            parts.append(ctx["title"])
        if ctx.get("compareTitle"):
            parts.append(f"对比主题={ctx['compareTitle']}")
        context_lines.append("；".join(parts))
    context_block = "\n".join(context_lines)
    summary_block = "\n\n---\n\n".join(summaries)

    if answer_mode == "data_only":
        system_prompt = (
            "你是中文教育数据分析助手。用户问题如果明显询问平台数据库里的数量、分布、排名、对比、年份变化等数据事实，"
            "必须严格依据【数据摘要】回答，不得编造数据库中没有的具体数值、项目、学校或结论。"
            "如果平台没有该省份或该维度的数据，要明确说明当前平台暂无相应数据。回答时先给结论，再列依据。"
        )
    elif answer_mode == "data_plus_reasoning":
        system_prompt = (
            "你是中文教育数据分析助手。回答分两层：第一层【数据库事实】只能依据【数据摘要】；"
            "第二层【解释和推断】可以结合教育评价、高等教育治理、区域产业和教学成果奖申报的一般知识，"
            "但必须明确这是推断或建议，不得说成数据库已经证明。"
        )
    elif answer_mode == "contextual_general":
        system_prompt = (
            "你是中文教育分析与教学成果奖申报咨询助手。"
            "当用户提出题目推荐、选题方向、命名、申报写作、原因解释、优化建议等开放型问题时，"
            "可以结合通用知识、教育领域经验、区域高教和产业背景正常回答。"
            "如果平台提供了【数据摘要】，涉及数据库事实时必须以摘要为准；"
            "如果用户提到的省份或主题暂无平台数据，也不要拒答，而是说明平台暂无该省份数据，"
            "随后基于一般知识和申报经验给出建议。请避免把建议伪装成数据库事实。"
        )
    else:
        system_prompt = (
            "你是中文通用智能助手，同时熟悉教学成果奖、高等教育治理、教育评价和申报写作。"
            "当问题不依赖平台数据库时，直接自然回答，不要强行局限于当前页面查询结果。"
        )

    data_notice = ""
    if requested_region and not has_platform_data:
        data_notice = f"平台当前暂无“{requested_region}”的结构化数据库数据；如需回答开放型建议，可结合通用知识和申报经验。"
    compare_notice = ""
    if len(compare_contexts) >= 2:
        compare_notice = "当前问题来自对比面板。回答必须同时分析左侧和右侧两个对比项，先分别概括双方数据，再指出共同点、差异和可能原因。不得只分析其中一侧。"

    user_content = (
        f"【用户明确提到的地区】\n{requested_region or '无'}\n\n"
        f"【用于数据库查询的省份】\n{province_display_name(province) if has_platform_data else province}\n\n"
        f"【回答模式】\n{answer_mode}\n\n"
        f"【查询上下文】\n{context_block or '无'}\n\n"
        f"【数据摘要】\n{summary_block or '无'}\n\n"
        f"【对比分析要求】\n{compare_notice or '无'}\n\n"
        f"【数据覆盖提示】\n{data_notice or '无'}\n\n"
        f"【用户问题】\n{question}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in CHAT_SESSIONS.get(session_id, [])[-10:]:
        if h["role"] in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_content})

    _append_session(session_id, "user", question)

    @stream_with_context
    def generate():
        full_answer = ""
        yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
        try:
            for chunk in deepseek_chat_stream(messages):
                if not chunk:
                    continue
                full_answer += chunk
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk}, ensure_ascii=False)}\n\n"
                time.sleep(0.012)

            full_answer = full_answer.strip() or "（无回答）"
            _append_session(session_id, "assistant", full_answer)
            yield f"data: {json.dumps({'type': 'done', 'answer': full_answer}, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_text = f"调用大模型失败：{str(e)}"
            _append_session(session_id, "assistant", err_text)
            yield f"data: {json.dumps({'type': 'error', 'error': err_text}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# =========================
# 启动
# =========================避免Restarting with stat
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
