"""
Importeur Open Food Facts local depuis le fichier Parquet Hugging Face.
Activé via OFF_LOCAL_ENABLED=true dans l'environnement.
"""
import os
import json
import logging
import time
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATA_DIR             = os.getenv("DATA_DIR", "/data")
OFF_LOCAL_ENABLED    = os.getenv("OFF_LOCAL_ENABLED", "false").lower() == "true"
OFF_COUNTRIES        = [c.strip() for c in os.getenv("OFF_COUNTRIES", "en:france").split(",") if c.strip()]
OFF_UPDATE_INTERVAL  = os.getenv("OFF_UPDATE_INTERVAL", "monthly")
OFF_SKIP_UPDATE      = os.getenv("OFF_SKIP_UPDATE", "false").lower() == "true"

PARQUET_URL  = "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet?download=true"
PARQUET_PATH = os.path.join(DATA_DIR, "off_food.parquet")
META_PATH    = os.path.join(DATA_DIR, "off_import_meta.json")

COLUMNS = [
    "code", "product_name", "brands", "nutriments",
    "countries_tags", "last_modified_t", "last_updated_t",
    "images", "obsolete",
]

INTERVALS = {
    "weekly":  7  * 24 * 3600,
    "monthly": 30 * 24 * 3600,
    "never":   None,
}


def _read_meta() -> dict:
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_meta(meta: dict):
    with open(META_PATH, "w") as f:
        json.dump(meta, f)


def _needs_update() -> bool:
    if OFF_SKIP_UPDATE:
        return False
    interval = INTERVALS.get(OFF_UPDATE_INTERVAL)
    if interval is None:
        return False
    meta = _read_meta()
    last = meta.get("last_import_ts", 0)
    return (time.time() - last) > interval


def _has_off_data(db_path: str) -> bool:
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM off_foods").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def download_parquet():
    logger.info("[OFF] Téléchargement du fichier Parquet depuis Hugging Face...")
    tmp_path = PARQUET_PATH + ".tmp"
    req = urllib.request.Request(PARQUET_URL, headers={
        "User-Agent": os.getenv("OFF_USER_AGENT", "FoodViseur/1.0 (self-hosted)")
    })
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = r.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and downloaded % (100 * 1024 * 1024) < chunk_size:
                        pct = downloaded * 100 // total
                        logger.info(f"[OFF] Téléchargement: {downloaded // (1024*1024)} Mo / {total // (1024*1024)} Mo ({pct}%)")
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e
    os.replace(tmp_path, PARQUET_PATH)
    logger.info(f"[OFF] Téléchargement terminé ({os.path.getsize(PARQUET_PATH) // (1024*1024)} Mo)")


def _safe_float(val, default=0.0) -> float:
    try:
        if val is None:
            return default
        f = float(val)
        return f if f >= 0 else default
    except (ValueError, TypeError):
        return default


def _parse_nutriments(nutriments) -> dict:
    """
    Extrait les macros depuis la liste de dicts nutriments du Parquet.
    Format : [{'name': 'fat', '100g': 48.0, ...}, ...]
    """
    result = {"calories": 0.0, "proteins": 0.0, "carbs": 0.0, "fats": 0.0, "fibers": 0.0}
    if not nutriments:
        return result

    # Mapping nom OFF → clé interne
    NAME_MAP = {
        "energy-kcal":          "calories",
        "proteins":             "proteins",
        "carbohydrates":        "carbs",
        "fat":                  "fats",
        "fiber":                "fibers",
        "fibers":               "fibers",
    }

    energy_kj = 0.0

    for n in nutriments:
        if not isinstance(n, dict):
            continue
        name = n.get("name", "")
        val_100g = n.get("100g")

        if name == "energy-kcal":
            result["calories"] = _safe_float(val_100g)
        elif name == "energy" and result["calories"] == 0.0:
            # fallback kJ → kcal
            energy_kj = _safe_float(val_100g)
        elif name in NAME_MAP and name != "energy-kcal":
            key = NAME_MAP[name]
            result[key] = _safe_float(val_100g)

    # Si pas de kcal direct, convertir depuis kJ
    if result["calories"] == 0.0 and energy_kj > 0:
        result["calories"] = round(energy_kj / 4.184, 1)

    return result


def _parse_product_name(product_name) -> str:
    """
    Format : [{'lang': 'main', 'text': '...'}, {'lang': 'fr', 'text': '...'}]
    Priorité : fr > main > premier disponible
    """
    if isinstance(product_name, str):
        return product_name.strip()
    if not isinstance(product_name, list) or not product_name:
        return ""

    fr_name = None
    main_name = None
    first_name = None

    for item in product_name:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        lang = item.get("lang", "")
        if lang == "fr":
            fr_name = text
        elif lang == "main" and main_name is None:
            main_name = text
        if first_name is None:
            first_name = text

    return fr_name or main_name or first_name or ""


def _parse_row(df: dict, i: int) -> tuple | None:
    """Parse une ligne du Parquet et retourne un tuple SQLite ou None si à ignorer."""
    # Obsolète
    obsolete = df.get("obsolete", [None] * len(df["code"]))[i]
    if obsolete:
        return None

    # Filtre pays
    countries = df["countries_tags"][i] or []
    if OFF_COUNTRIES and not any(c in countries for c in OFF_COUNTRIES):
        return None

    # Code-barres
    barcode = str(df["code"][i] or "").strip()
    if not barcode:
        return None

    # Nom
    name = _parse_product_name(df["product_name"][i])
    if not name:
        return None

    # Marque
    brands_raw = df["brands"][i]
    if isinstance(brands_raw, list):
        brand = str(brands_raw[0]).strip() if brands_raw else None
    elif isinstance(brands_raw, dict):
        brand = None
    else:
        brand = str(brands_raw or "").split(",")[0].strip() or None

    # Nutriments
    n = _parse_nutriments(df["nutriments"][i])

    # Image
    images = df["images"][i]
    image_url = None
    if isinstance(images, list):
        for img in images:
            if isinstance(img, dict) and img.get("key", "").startswith("front"):
                image_url = img.get("url")
                break

    # Timestamp effectif
    last_modified = int(df["last_modified_t"][i] or 0)
    last_updated  = int(df.get("last_updated_t", [0] * len(df["code"]))[i] or 0)
    effective_ts  = max(last_modified, last_updated)

    return (
        barcode, name, brand,
        n["calories"], n["proteins"], n["carbs"], n["fats"], n["fibers"],
        image_url,
        json.dumps(countries),
        effective_ts,
    )


def import_to_db(db_path: str):
    """Import complet depuis le Parquet."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        logger.error("[OFF] pyarrow non installé")
        return

    import sqlite3

    logger.info(f"[OFF] Import complet pour les pays : {OFF_COUNTRIES}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("DROP TABLE IF EXISTS off_foods")
    conn.execute("""
        CREATE TABLE off_foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            brand TEXT,
            calories_100g REAL DEFAULT 0,
            proteins_100g REAL DEFAULT 0,
            carbs_100g REAL DEFAULT 0,
            fats_100g REAL DEFAULT 0,
            fibers_100g REAL DEFAULT 0,
            image_url TEXT,
            countries_tags TEXT,
            last_modified_t INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_off_name    ON off_foods(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_off_barcode ON off_foods(barcode)")

    pf = pq.ParquetFile(PARQUET_PATH)
    total_inserted = 0
    total_skipped  = 0
    max_updated_t  = 0
    batch_size     = 10000

    for batch in pf.iter_batches(batch_size=batch_size, columns=COLUMNS):
        df = batch.to_pydict()
        rows = []
        for i in range(len(df["code"])):
            row = _parse_row(df, i)
            if row is None:
                total_skipped += 1
                continue
            if row[10] > max_updated_t:
                max_updated_t = row[10]
            rows.append(row)

        if rows:
            conn.executemany("""
                INSERT OR REPLACE INTO off_foods
                (barcode, name, brand, calories_100g, proteins_100g, carbs_100g,
                 fats_100g, fibers_100g, image_url, countries_tags, last_modified_t)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            total_inserted += len(rows)

        if (total_inserted + total_skipped) % 100000 < batch_size:
            logger.info(f"[OFF] Progression: {total_inserted} insérés, {total_skipped} ignorés...")

    conn.close()
    logger.info(f"[OFF] ✓ Import terminé : {total_inserted} produits insérés")

    _write_meta({
        "last_import_ts": time.time(),
        "countries":      OFF_COUNTRIES,
        "count":          total_inserted,
        "imported_at":    datetime.now(timezone.utc).isoformat(),
        "max_updated_t":  max_updated_t,
    })


def import_differential(db_path: str):
    """Import différentiel : uniquement les lignes modifiées depuis le dernier import."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        logger.error("[OFF] pyarrow non installé")
        return

    import sqlite3

    meta = _read_meta()
    last_max_ts = meta.get("max_updated_t", 0)

    if last_max_ts == 0:
        logger.info("[OFF] Pas de timestamp de référence, import complet")
        import_to_db(db_path)
        return

    logger.info(f"[OFF] Import différentiel depuis {datetime.fromtimestamp(last_max_ts, tz=timezone.utc).isoformat()}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    pf = pq.ParquetFile(PARQUET_PATH)
    total_updated = 0
    batch_size    = 10000

    for batch in pf.iter_batches(batch_size=batch_size, columns=COLUMNS):
        df = batch.to_pydict()
        rows = []
        for i in range(len(df["code"])):
            last_modified = int(df["last_modified_t"][i] or 0)
            last_updated  = int(df.get("last_updated_t", [0] * len(df["code"]))[i] or 0)
            effective_ts  = max(last_modified, last_updated)
            if effective_ts <= last_max_ts:
                continue
            row = _parse_row(df, i)
            if row is None:
                continue
            rows.append(row)

        if rows:
            conn.executemany("""
                INSERT OR REPLACE INTO off_foods
                (barcode, name, brand, calories_100g, proteins_100g, carbs_100g,
                 fats_100g, fibers_100g, image_url, countries_tags, last_modified_t)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            total_updated += len(rows)

    conn.close()
    logger.info(f"[OFF] ✓ Import différentiel : {total_updated} produits mis à jour")

    meta["last_import_ts"] = time.time()
    meta["imported_at"]    = datetime.now(timezone.utc).isoformat()
    _write_meta(meta)


def run_if_needed(db_path: str):
    if not OFF_LOCAL_ENABLED:
        return

    need_download = not os.path.exists(PARQUET_PATH)
    need_update   = _needs_update()

    if need_download:
        logger.info("[OFF] Fichier Parquet absent, téléchargement requis")
        try:
            download_parquet()
        except Exception as e:
            logger.error(f"[OFF] Échec téléchargement : {e}")
            return
    elif need_update:
        logger.info("[OFF] Mise à jour planifiée, re-téléchargement")
        try:
            download_parquet()
        except Exception as e:
            logger.error(f"[OFF] Échec mise à jour : {e} — import différentiel avec ancien fichier")
    else:
        meta = _read_meta()
        if _has_off_data(db_path):
            logger.info(f"[OFF] Base locale OK ({meta.get('count', 0)} produits, importé le {meta.get('imported_at', '?')})")
            return
        logger.info("[OFF] Table off_foods vide, re-import depuis le cache")

    try:
        meta = _read_meta()
        if meta.get("max_updated_t", 0) > 0 and _has_off_data(db_path) and not need_download:
            import_differential(db_path)
        else:
            import_to_db(db_path)
    except Exception as e:
        logger.error(f"[OFF] Échec import : {e}")
        import traceback
        logger.error(traceback.format_exc())
