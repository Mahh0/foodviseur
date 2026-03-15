"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-03-14
"""
from alembic import op
import sqlalchemy as sa
import os, json, logging, urllib.request, xml.etree.ElementTree as ET

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.ciqual")

DATASET_DOI = "doi:10.57745/RDMHWY"
API_BASE    = "https://entrepot.recherche.data.gouv.fr/api"
DATA_DIR    = os.getenv("DATA_DIR", "/data")

# Codes INFOODS → colonne (vérifiés sur CIQUAL 2025)
MACRO_CODES = {
    "ENERC":  "calories_100g",   # kcal — on filtrera sur kcal vs kJ
    "PROCNT": "proteins_100g",   # Protéines (N x facteur Jones)
    "CHOAVL": "carbs_100g",      # Glucides disponibles
    "FAT":    "fats_100g",       # Lipides
    "FIB-":   "fibers_100g",     # Fibres
}
ENERC_UNIT_FILTER = "kcal"

TARGET_FILES = {
    "alim_2025_11_03.xml":  "ciqual_alim.xml",
    "const_2025_11_03.xml": "ciqual_const.xml",
    "compo_2025_11_03.xml": "ciqual_compo.xml",
}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "FoodViseur/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _txt(elem, tag):
    child = elem.find(tag)
    if child is None:
        for c in elem:
            if c.tag.lower() == tag.lower():
                return (c.text or "").strip()
        return ""
    return (child.text or "").strip()


def _parse_val(raw):
    if not raw or raw.strip() in ("-", "", "traces", "Traces"):
        return 0.0
    v = raw.strip().replace(",", ".").replace("<", "").replace(">", "")
    try:
        return float(v)
    except ValueError:
        return 0.0


def _get_file_ids():
    url  = f"{API_BASE}/datasets/:persistentId/?persistentId={DATASET_DOI}"
    data = json.loads(_get(url))
    files = data.get("data", {}).get("latestVersion", {}).get("files", [])
    result = {}
    for f in files:
        label = f.get("label", "")
        fid   = f.get("dataFile", {}).get("id")
        if label in TARGET_FILES and fid:
            result[label] = fid
    return result


def _download(file_id, dest, label):
    if os.path.exists(dest):
        logger.info(f"[CIQUAL] {label} déjà en cache, skip")
        return
    logger.info(f"[CIQUAL] Téléchargement {label}...")
    data = _get(f"{API_BASE}/access/datafile/{file_id}", timeout=180)
    with open(dest, "wb") as f:
        f.write(data)
    logger.info(f"[CIQUAL] {label} OK ({os.path.getsize(dest)//1024} KB)")


def upgrade():
    # ── Schéma complet ──────────────────────────────────────────
    op.create_table("goals",
        sa.Column("id",         sa.Integer(), primary_key=True),
        sa.Column("calories",   sa.Float(),   default=2000.0),
        sa.Column("proteins",   sa.Float(),   default=150.0),
        sa.Column("carbs",      sa.Float(),   default=250.0),
        sa.Column("fats",       sa.Float(),   default=70.0),
        sa.Column("fibers",     sa.Float(),   default=25.0),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table("food_cache",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("barcode",       sa.String(),  unique=True, index=True, nullable=True),
        sa.Column("off_id",        sa.String(),  unique=True, index=True, nullable=True),
        sa.Column("name",          sa.String(),  nullable=False),
        sa.Column("brand",         sa.String(),  nullable=True),
        sa.Column("calories_100g", sa.Float(),   default=0.0),
        sa.Column("proteins_100g", sa.Float(),   default=0.0),
        sa.Column("carbs_100g",    sa.Float(),   default=0.0),
        sa.Column("fats_100g",     sa.Float(),   default=0.0),
        sa.Column("fibers_100g",   sa.Float(),   default=0.0),
        sa.Column("image_url",     sa.String(),  nullable=True),
        sa.Column("cached_at",     sa.DateTime()),
        sa.Column("is_custom",     sa.Boolean(), default=False, nullable=False, server_default="0"),
    )

    op.create_table("meal_entries",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("date",          sa.Date(),    index=True),
        sa.Column("logged_at",     sa.DateTime()),
        sa.Column("meal_type",     sa.String(),  default="dejeuner", nullable=False),
        sa.Column("food_name",     sa.String(),  nullable=False),
        sa.Column("brand",         sa.String(),  nullable=True),
        sa.Column("quantity_g",    sa.Float(),   nullable=False),
        sa.Column("calories",      sa.Float(),   default=0.0),
        sa.Column("proteins",      sa.Float(),   default=0.0),
        sa.Column("carbs",         sa.Float(),   default=0.0),
        sa.Column("fats",          sa.Float(),   default=0.0),
        sa.Column("fibers",        sa.Float(),   default=0.0),
        sa.Column("calories_100g", sa.Float(),   default=0.0),
        sa.Column("proteins_100g", sa.Float(),   default=0.0),
        sa.Column("carbs_100g",    sa.Float(),   default=0.0),
        sa.Column("fats_100g",     sa.Float(),   default=0.0),
        sa.Column("fibers_100g",   sa.Float(),   default=0.0),
        sa.Column("notes",         sa.Text(),    nullable=True),
        sa.Column("food_cache_id", sa.Integer(), nullable=True),
    )

    op.create_table("ciqual_foods",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("ciqual_code",   sa.Integer(), unique=True, index=True, nullable=False),
        sa.Column("name_fr",       sa.String(),  nullable=False, index=True),
        sa.Column("calories_100g", sa.Float(),   default=0.0),
        sa.Column("proteins_100g", sa.Float(),   default=0.0),
        sa.Column("carbs_100g",    sa.Float(),   default=0.0),
        sa.Column("fats_100g",     sa.Float(),   default=0.0),
        sa.Column("fibers_100g",   sa.Float(),   default=0.0),
    )

    # ── Import CIQUAL ───────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        logger.info("[CIQUAL] Récupération des IDs de fichiers...")
        file_ids = _get_file_ids()
        logger.info(f"[CIQUAL] Fichiers : {file_ids}")
    except Exception as e:
        logger.error(f"[CIQUAL] Impossible de récupérer les IDs : {e}")
        logger.error("[CIQUAL] Table créée vide. Relancez pour réessayer.")
        return

    paths = {}
    try:
        for original_name, local_name in TARGET_FILES.items():
            dest = os.path.join(DATA_DIR, local_name)
            fid  = file_ids.get(original_name)
            if fid:
                _download(fid, dest, original_name)
            elif os.path.exists(dest):
                logger.info(f"[CIQUAL] {local_name} déjà présent")
            else:
                raise Exception(f"{original_name} introuvable")
            paths[local_name] = dest
    except Exception as e:
        logger.error(f"[CIQUAL] Erreur téléchargement : {e}")
        return

    # Parser const.xml → code numérique → colonne
    logger.info("[CIQUAL] Parsing constituants...")
    const_map = {}
    try:
        root = ET.parse(paths["ciqual_const.xml"]).getroot()
        for elem in root.iter("CONST"):
            code_str = _txt(elem, "const_code")
            infoods  = _txt(elem, "code_INFOODS")
            nom_fr   = _txt(elem, "const_nom_fr").lower()
            if not code_str or infoods not in MACRO_CODES:
                continue
            if infoods == "ENERC" and ENERC_UNIT_FILTER not in nom_fr:
                continue
            try:
                const_map[int(code_str)] = MACRO_CODES[infoods]
            except ValueError:
                pass
    except Exception as e:
        logger.error(f"[CIQUAL] Erreur parsing const : {e}")
        return

    logger.info(f"[CIQUAL] Codes macros trouvés : {const_map}")
    if not const_map:
        logger.error("[CIQUAL] Aucun code macro trouvé")
        return

    # Parser alim.xml
    logger.info("[CIQUAL] Parsing aliments...")
    alim_names = {}
    try:
        root = ET.parse(paths["ciqual_alim.xml"]).getroot()
        for elem in root.iter("ALIM"):
            code_str = _txt(elem, "alim_code")
            name     = _txt(elem, "alim_nom_fr")
            if code_str and name:
                try:
                    alim_names[int(code_str)] = name
                except ValueError:
                    pass
    except Exception as e:
        logger.error(f"[CIQUAL] Erreur parsing alim : {e}")
        return

    logger.info(f"[CIQUAL] {len(alim_names)} aliments chargés")

    # Parser compo.xml
    logger.info("[CIQUAL] Parsing composition (~66MB)...")
    nutrients = {}
    try:
        root = ET.parse(paths["ciqual_compo.xml"]).getroot()
        for elem in root.iter("COMPO"):
            alim_str  = _txt(elem, "alim_code")
            const_str = _txt(elem, "const_code")
            teneur    = _txt(elem, "teneur")
            if not alim_str or not const_str:
                continue
            try:
                alim_code  = int(alim_str)
                const_code = int(const_str)
            except ValueError:
                continue
            col = const_map.get(const_code)
            if col is None:
                continue
            if alim_code not in nutrients:
                nutrients[alim_code] = {}
            nutrients[alim_code][col] = _parse_val(teneur)
    except Exception as e:
        logger.error(f"[CIQUAL] Erreur parsing compo : {e}")
        return

    logger.info(f"[CIQUAL] {len(nutrients)} aliments avec données")

    # Insertion
    logger.info("[CIQUAL] Insertion en base...")
    conn  = op.get_bind()
    table = sa.table("ciqual_foods",
        sa.column("ciqual_code",   sa.Integer),
        sa.column("name_fr",       sa.String),
        sa.column("calories_100g", sa.Float),
        sa.column("proteins_100g", sa.Float),
        sa.column("carbs_100g",    sa.Float),
        sa.column("fats_100g",     sa.Float),
        sa.column("fibers_100g",   sa.Float),
    )
    batch = []
    for code, name in alim_names.items():
        n = nutrients.get(code, {})
        batch.append({
            "ciqual_code":   code,
            "name_fr":       name,
            "calories_100g": n.get("calories_100g", 0.0),
            "proteins_100g": n.get("proteins_100g", 0.0),
            "carbs_100g":    n.get("carbs_100g",    0.0),
            "fats_100g":     n.get("fats_100g",     0.0),
            "fibers_100g":   n.get("fibers_100g",   0.0),
        })
        if len(batch) >= 500:
            conn.execute(table.insert(), batch)
            batch = []
    if batch:
        conn.execute(table.insert(), batch)

    logger.info(f"[CIQUAL] ✓ {len(alim_names)} aliments insérés")


def downgrade():
    op.drop_table("ciqual_foods")
    op.drop_table("meal_entries")
    op.drop_table("food_cache")
    op.drop_table("goals")
    for fname in ("ciqual_alim.xml", "ciqual_compo.xml", "ciqual_const.xml"):
        p = os.path.join(DATA_DIR, fname)
        if os.path.exists(p):
            os.remove(p)
