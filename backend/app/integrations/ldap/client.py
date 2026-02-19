import logging
import os

from ldap3 import ALL, NTLM, SUBTREE, Connection, Server
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

LDAP_SERVER = os.getenv("LDAP_SERVER")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")
LDAP_USER = os.getenv("LDAP_USER")
LDAP_PASS = os.getenv("LDAP_PASS")


def ldap_authenticate(username, password):
    try:
        user_dn = f"{LDAP_DOMAIN}\\{username}"
        server = Server(LDAP_SERVER, get_info=ALL, use_ssl=True)
        conn = Connection(server, user=user_dn, password=password, authentication=NTLM, auto_bind=True)
        conn.unbind()
        return True
    except Exception:
        return False


def search_ldap_users(query, page_size=500):
    try:
        ldap_base_dn = f"DC={LDAP_DOMAIN.replace('.', ',DC=')}"
        server = Server(LDAP_SERVER, get_info=ALL, use_ssl=True)
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            logger.info(f"LDAP connection successful. Search query: {query}")
            escaped_query = escape_filter_chars(str(query))
            search_filter = f"(|(sAMAccountName=*{escaped_query}*)(mail=*{escaped_query}*))"
            attributes = ["name", "sAMAccountName", "distinguishedName", "mail"]
            total_entries, entry_count, cookie = [], 0, None
            while True:
                conn.search(
                    search_base=ldap_base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                    paged_size=page_size,
                    paged_cookie=cookie,
                )
                results = []
                for entry in conn.entries:
                    entry_count += 1
                    logger.debug(f"Processing entry {entry_count}")
                    if entry.sAMAccountName and entry.mail and entry.name:
                        results.append(
                            {
                                "username": str(entry.sAMAccountName.value),
                                "email": str(entry.mail.value),
                                "full_name": str(entry.name.value),
                                "distinguished_name": str(entry.distinguishedName.value)
                                if entry.distinguishedName
                                else None,
                            }
                        )
                total_entries.extend(results)
                logger.info(f"Retrieved {len(results)} entries in the current page")
                cookie = (
                    conn.result.get("controls", {})
                    .get("1.2.840.113556.1.4.319", {})
                    .get("value", {})
                    .get("cookie")
                )
                if not cookie:
                    break
            logger.info(f"Total entries retrieved: {len(total_entries)}")
            return total_entries
    except Exception as exc:
        logger.error(f"Error searching LDAP: {exc}")
        raise RuntimeError(f"LDAP search failed: {exc}")


__all__ = ["ldap_authenticate", "search_ldap_users"]
