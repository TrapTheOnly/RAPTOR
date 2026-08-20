import logging
import re

from flask import jsonify, request, session

from app.config import DB_PATH
from app.http.decorators.permission_required import permission_required
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.integrations.storage.offsec_storage import save_image

logger = logging.getLogger(__name__)

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_KIT = {
    "company_name": "Security Operations",
    "print_ink": "#067A8A",
    "logo_asset_id": None,
    "logo_url": "",
}


def _row_to_kit(row, logo_path=None):
    if not row:
        return dict(DEFAULT_KIT)
    data = dict(row) if not isinstance(row, dict) else row
    logo_asset_id = data.get("logo_asset_id")
    logo_url = f"/pentest/images/{logo_path}" if logo_path else ""
    return {
        "company_name": str(data.get("company_name") or DEFAULT_KIT["company_name"]),
        "print_ink": str(data.get("print_ink") or DEFAULT_KIT["print_ink"]),
        "logo_asset_id": int(logo_asset_id) if logo_asset_id else None,
        "logo_url": logo_url,
        "updated_by": data.get("updated_by") or "",
        "updated_at": data.get("updated_at") or "",
    }


def _logo_path_for(cursor, logo_asset_id):
    if not logo_asset_id:
        return None
    cursor.execute("SELECT file_path FROM report_kit_logo_assets WHERE id = ?", (int(logo_asset_id),))
    row = cursor.fetchone()
    if not row:
        return None
    return str(row["file_path"] if isinstance(row, dict) else row[0] or "").strip() or None


def fetch_brand_kit(cursor=None):
    def _load(active):
        try:
            active.execute("SELECT * FROM report_brand_kits WHERE id = 1")
        except Exception:
            return dict(DEFAULT_KIT)
        row = active.fetchone()
        logo_path = _logo_path_for(active, (row or {}).get("logo_asset_id") if row else None)
        return _row_to_kit(row, logo_path)

    if cursor is not None:
        return _load(cursor)
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        return _load(conn.cursor())


def apply_brand_kit(template_definition, kit):
    next_definition = dict(template_definition or {})
    branding = dict(next_definition.get("branding") or {}) if isinstance(next_definition.get("branding"), dict) else {}
    if kit:
        if kit.get("company_name"):
            branding["company_name"] = kit["company_name"]
        if kit.get("print_ink"):
            branding["primary_color"] = kit["print_ink"]
        if kit.get("logo_url"):
            branding["logo_url"] = kit["logo_url"]
            branding["logo_asset_id"] = kit.get("logo_asset_id")
    next_definition["branding"] = branding
    return next_definition


@permission_required("manage_report_templates")
def get_report_brand_kit():
    try:
        return jsonify({"kit": fetch_brand_kit()}), 200
    except Exception as exc:
        logger.error("Failed to load report brand kit: %s", exc)
        return jsonify({"error": "Failed to load brand kit."}), 500


@permission_required("manage_report_templates")
def update_report_brand_kit():
    payload = request.get_json(silent=True) or {}
    company_name = re.sub(r"[\x00-\x1F\x7F]", "", str(payload.get("company_name") or "")).strip()[:120]
    if not company_name:
        company_name = DEFAULT_KIT["company_name"]
    print_ink = str(payload.get("print_ink") or "").strip()
    if not HEX_COLOR_PATTERN.fullmatch(print_ink):
        print_ink = DEFAULT_KIT["print_ink"]
    username = session.get("username") or ""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            existing = fetch_brand_kit(c)
            logo_asset_id = existing.get("logo_asset_id")
            if "logo_asset_id" in payload:
                raw = payload.get("logo_asset_id")
                if raw in (None, "", 0, "0"):
                    logo_asset_id = None
                else:
                    logo_asset_id = int(raw)
            c.execute(
                """
                INSERT INTO report_brand_kits (id, company_name, print_ink, logo_asset_id, updated_by, updated_at)
                VALUES (1, ?, ?, ?, ?, (NOW() + INTERVAL '4 hours'))
                ON CONFLICT (id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    print_ink = EXCLUDED.print_ink,
                    logo_asset_id = EXCLUDED.logo_asset_id,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (company_name, print_ink, logo_asset_id, username),
            )
            conn.commit()
        return jsonify({"kit": fetch_brand_kit()}), 200
    except Exception as exc:
        logger.error("Failed to update report brand kit: %s", exc)
        return jsonify({"error": "Failed to update brand kit."}), 500


@permission_required("manage_report_templates")
def upload_report_brand_kit_logo():
    from app.services.offsec.offsec_templates import _validate_report_logo_file

    file_storage = request.files.get("logo")
    file_data, error = _validate_report_logo_file(file_storage)
    if error:
        return jsonify({"error": error}), 400
    try:
        filename = save_image(file_data, "png")
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO report_kit_logo_assets (file_path, created_by, created_at)
                VALUES (?, ?, (NOW() + INTERVAL '4 hours'))
                RETURNING id
                """,
                (filename, session.get("username") or ""),
            )
            inserted = c.fetchone()
            logo_asset_id = inserted["id"] if isinstance(inserted, dict) else inserted[0]
            existing = fetch_brand_kit(c)
            c.execute(
                """
                INSERT INTO report_brand_kits (id, company_name, print_ink, logo_asset_id, updated_by, updated_at)
                VALUES (1, ?, ?, ?, ?, (NOW() + INTERVAL '4 hours'))
                ON CONFLICT (id) DO UPDATE SET
                    logo_asset_id = EXCLUDED.logo_asset_id,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    existing.get("company_name") or DEFAULT_KIT["company_name"],
                    existing.get("print_ink") or DEFAULT_KIT["print_ink"],
                    logo_asset_id,
                    session.get("username") or "",
                ),
            )
            conn.commit()
        kit = fetch_brand_kit()
        return jsonify({"kit": kit, "logo_asset_id": logo_asset_id, "logo_url": kit.get("logo_url")}), 200
    except Exception as exc:
        logger.error("Failed to upload brand kit logo: %s", exc)
        return jsonify({"error": "Failed to upload logo."}), 500
