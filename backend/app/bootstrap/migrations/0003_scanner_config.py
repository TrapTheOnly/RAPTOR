"""Add scanner_config table for AI scanner settings."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scanner_config (
            id SERIAL PRIMARY KEY,
            aws_region TEXT NOT NULL DEFAULT 'us-east-1',
            bedrock_model_id TEXT NOT NULL DEFAULT '',
            cost_limit_usd NUMERIC(10,4) NOT NULL DEFAULT 5.0,
            input_cost_per_1m NUMERIC(10,6) NOT NULL DEFAULT 3.0,
            output_cost_per_1m NUMERIC(10,6) NOT NULL DEFAULT 15.0,
            max_concurrent_scans INTEGER NOT NULL DEFAULT 2,
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cursor.execute("SELECT COUNT(*) FROM scanner_config")
    row = cursor.fetchone()
    count = row[0] if row and not isinstance(row, dict) else (row.get("count", 0) if row else 0)
    if int(count) == 0:
        cursor.execute(
            """
            INSERT INTO scanner_config (
                aws_region, bedrock_model_id, cost_limit_usd,
                input_cost_per_1m, output_cost_per_1m,
                max_concurrent_scans, enabled, updated_at
            ) VALUES ('us-east-1', '', 5.0, 3.0, 15.0, 2, 0, (NOW() + INTERVAL '4 hours'))
            """
        )
