"""CIQUAL 2025 - création table et import données

Revision ID: 0003
Revises: 0002_meal_type_and_100g
Create Date: 2025-03-13
"""
from alembic import op
import sqlalchemy as sa
import os, json, logging, urllib.request, xml.etree.ElementTree as ET

revision = '0003'
down_revision = '0002_meal_type_and_100g'
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.ciqual")

DATASET_DOI = "doi:10.57745/RDMHWY"
API_BASE    = "https://entrepot.recherche.data.gouv.fr/api"
DATA_DIR    = os.getenv("DATA_DIR", "/data")

# Code INFOODS → colonne
# ENERC apparaît en kJ (327) ET kcal (328) — on veut kcal (328)
# On filtre par nom FR pour choisir la bonne ligne
MACRO_INFOODS = {
    "ENERC":  "calories_100g",
    "PROT":   "proteins_100g",
    "CHOAVL": "carbs_100g",
    "FAT":    "fats_100g",
}

# Pour ENERC on veut uniquement la ligne kcal (pas kJ)
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
    """Récupère le texte d'un sous-élément en ignorant la casse et les espaces."""
    child = elem.find(tag)
    if child is None:
        # Essai insensible à la casse
        for c in elem:
            if c.tag.lower() == tag.lower():
                return (c.text or "").strip()
        return ""
    return (child.text or "").strip()


def _get_file_ids() -> dict:
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


def _download(file_id: int, dest: str, label: str):
    if os.path.exists(dest):
        logger.info(f"[CIQUAL] {label} déjà en cache, skip")
        return
    logger.info(f"[CIQUAL] Téléchargement {label} (id={file_id})...")
    data = _get(f"{API_BASE}/access/datafile/{file_id}", timeout=180)
    with open(dest, "wb") as f:
        f.write(data)
    logger.info(f"[CIQUAL] {label} OK ({os.path.getsize(dest)//1024} KB)")


def _parse_val(raw):
    if not raw or raw.strip() in ("-", "", "traces", "Traces"):
        return 0.0
    v = raw.strip().replace(",", ".").replace("<", "").replace(">", "")
    try:
        return float(v)
    except ValueError:
        return 0.0


def upgrade():
    op.create_table(
        "ciqual_foods",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("ciqual_code",   sa.Integer(), nullable=False, unique=True, index=True),
        sa.Column("name_fr",       sa.String(),  nullable=False, index=True),
        sa.Column("calories_100g", sa.Float(),   default=0.0),
        sa.Column("proteins_100g", sa.Float(),   default=0.0),
        sa.Column("carbs_100g",    sa.Float(),   default=0.0),
        sa.Column("fats_100g",     sa.Float(),   default=0.0),
    )

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. IDs fichiers
    try:
        logger.info("[CIQUAL] Récupération des IDs de fichiers...")
        file_ids = _get_file_ids()
        logger.info(f"[CIQUAL] Fichiers : {file_ids}")
    except Exception as e:
        logger.error(f"[CIQUAL] Impossible de récupérer les IDs : {e}")
        logger.error("[CIQUAL] Table créée vide. Relancez le conteneur pour réessayer.")
        return

    # 2. Téléchargements
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
                raise Exception(f"{original_name} introuvable dans le dataset")
            paths[local_name] = dest
    except Exception as e:
        logger.error(f"[CIQUAL] Erreur téléchargement : {e}")
        logger.error("[CIQUAL] Table créée vide. Relancez le conteneur pour réessayer.")
        return

    # 3. Parser const.xml → code numérique → colonne
    # Structure : <TABLE><CONST><const_code>327</const_code><code_INFOODS>ENERC</code_INFOODS>...
    logger.info("[CIQUAL] Parsing constituants...")
    const_map = {}  # int(const_code) → colonne
    try:
        root = ET.parse(paths["ciqual_const.xml"]).getroot()
        for elem in root.iter("CONST"):
            code_str    = _txt(elem, "const_code")
            infoods     = _txt(elem, "code_INFOODS")
            nom_fr      = _txt(elem, "const_nom_fr").lower()

            if not code_str or infoods not in MACRO_INFOODS:
                continue

            # Pour ENERC : ne garder que la ligne kcal (pas kJ)
            if infoods == "ENERC" and ENERC_UNIT_FILTER not in nom_fr:
                continue

            try:
                const_map[int(code_str)] = MACRO_INFOODS[infoods]
            except ValueError:
                pass

    except Exception as e:
        logger.error(f"[CIQUAL] Erreur parsing const : {e}")
        return

    logger.info(f"[CIQUAL] Codes macros trouvés : {const_map}")
    if not const_map:
        logger.error("[CIQUAL] Aucun code macro trouvé — vérifier la structure du XML")
        return

    # 4. Parser alim.xml → alim_code → name_fr
    # Structure : <TABLE><ALIM><alim_code>1000</alim_code><alim_nom_fr>Pastis</alim_nom_fr>...
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

    # 5. Parser compo.xml → valeurs nutritionnelles
    # Structure : <TABLE><COMPO><alim_code>...</alim_code><const_code>...</const_code><teneur>...</teneur>
    logger.info("[CIQUAL] Parsing composition (~66MB, patience...)...")
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

    logger.info(f"[CIQUAL] {len(nutrients)} aliments avec données nutritionnelles")

    # 6. Insertion en base
    logger.info("[CIQUAL] Insertion en base...")
    conn  = op.get_bind()
    table = sa.table(
        "ciqual_foods",
        sa.column("ciqual_code",   sa.Integer),
        sa.column("name_fr",       sa.String),
        sa.column("calories_100g", sa.Float),
        sa.column("proteins_100g", sa.Float),
        sa.column("carbs_100g",    sa.Float),
        sa.column("fats_100g",     sa.Float),
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
        })
        if len(batch) >= 500:
            conn.execute(table.insert(), batch)
            batch = []
    if batch:
        conn.execute(table.insert(), batch)

    logger.info(f"[CIQUAL] ✓ {len(alim_names)} aliments insérés")


def downgrade():
    op.drop_table("ciqual_foods")
    for fname in ("ciqual_alim.xml", "ciqual_compo.xml", "ciqual_const.xml"):
        p = os.path.join(DATA_DIR, fname)
        if os.path.exists(p):
            os.remove(p)
