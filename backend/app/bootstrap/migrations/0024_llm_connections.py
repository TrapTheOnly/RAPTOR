"""LLM connections catalog and scanner_config active-model columns."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_connections (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            models JSONB NOT NULL DEFAULT '[]'::jsonb,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_checked_at TEXT,
            last_error TEXT NOT NULL DEFAULT '',
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS llm_connections_local_unique
        ON llm_connections (type)
        WHERE type = 'local'
        """
    )
    _add_column(cursor, "scanner_config", "active_connection_id", "INTEGER")
    _add_column(cursor, "scanner_config", "active_model_id", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "scanner_config", "thinking_budget_tokens", "INTEGER NOT NULL DEFAULT 8000")
    _add_column(cursor, "scanner_config", "max_turns", "INTEGER NOT NULL DEFAULT 40")

    cursor.execute("SELECT id FROM llm_connections WHERE type = 'local' ORDER BY id ASC LIMIT 1")
    local_row = cursor.fetchone()
    if not local_row:
        cursor.execute(
            """
            INSERT INTO llm_connections (type, display_name, config, models, enabled, updated_at)
            VALUES (
                'local',
                'RAPTOR Local',
                '{}'::jsonb,
                '[{"id":"qwen3.6-27b","display_name":"Qwen3.6 27B (Unsloth Q4)","source":"bundled","selected":true,"tools":true,"thinking":false,"input_cost_per_1m":0,"output_cost_per_1m":0}]'::jsonb,
                1,
                (NOW() AT TIME ZONE 'utc')::text
            )
            """
        )

    cursor.execute(
        "SELECT id, aws_region, bedrock_model_id, active_connection_id FROM scanner_config ORDER BY id ASC LIMIT 1"
    )
    cfg = cursor.fetchone()
    if not cfg:
        return
    cfg_id = cfg["id"] if isinstance(cfg, dict) else cfg[0]
    aws_region = (cfg["aws_region"] if isinstance(cfg, dict) else cfg[1]) or "us-east-1"
    bedrock_model_id = str((cfg["bedrock_model_id"] if isinstance(cfg, dict) else cfg[2]) or "").strip()
    active_connection_id = cfg["active_connection_id"] if isinstance(cfg, dict) else cfg[3]
    if bedrock_model_id and not active_connection_id:
        models = [
            {
                "id": bedrock_model_id,
                "display_name": bedrock_model_id,
                "source": "manual",
                "selected": True,
                "tools": True,
                "thinking": True,
            }
        ]
        import json

        cursor.execute(
            """
            INSERT INTO llm_connections (type, display_name, config, models, enabled, updated_at)
            VALUES ('bedrock', 'AWS Bedrock', ?::jsonb, ?::jsonb, 1, (NOW() AT TIME ZONE 'utc')::text)
            RETURNING id
            """,
            (json.dumps({"aws_region": aws_region}), json.dumps(models)),
        )
        inserted = cursor.fetchone()
        new_id = inserted["id"] if isinstance(inserted, dict) else inserted[0]
        cursor.execute(
            "UPDATE scanner_config SET active_connection_id = ?, active_model_id = ? WHERE id = ?",
            (new_id, bedrock_model_id, cfg_id),
        )
