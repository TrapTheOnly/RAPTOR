"""Disable legacy bind_file drop-folder DNS sources."""


def up(cursor):
    cursor.execute("UPDATE dns_sources SET enabled = 0 WHERE type = 'bind_file'")
