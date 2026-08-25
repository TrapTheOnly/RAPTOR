"""Allow deleting a DNS connector without deleting its observation history."""


def up(cursor):
    cursor.execute("ALTER TABLE dns_observations ALTER COLUMN source_id DROP NOT NULL")
    cursor.execute(
        """
        SELECT conname, pg_get_constraintdef(oid) AS def
        FROM pg_constraint
        WHERE conrelid = 'dns_observations'::regclass
          AND contype = 'f'
        """
    )
    already_set_null = False
    for row in cursor.fetchall() or []:
        name = row["conname"] if isinstance(row, dict) else row[0]
        definition = str(row["def"] if isinstance(row, dict) else row[1])
        if "source_id" not in definition:
            continue
        if "ON DELETE SET NULL" in definition.upper():
            already_set_null = True
            continue
        cursor.execute(f'ALTER TABLE dns_observations DROP CONSTRAINT IF EXISTS "{name}"')
    if already_set_null:
        return
    cursor.execute(
        """
        ALTER TABLE dns_observations
        ADD CONSTRAINT dns_observations_source_id_fkey
        FOREIGN KEY (source_id) REFERENCES dns_sources(id) ON DELETE SET NULL
        """
    )
