import os
import logging
from flask import session, jsonify, redirect
from functools import wraps
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from adminhandler import admin_login

# Configure logging
logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
LDAP_SERVER = os.getenv("LDAP_SERVER")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")
LDAP_USER = os.getenv("LDAP_USER")
LDAP_PASS = os.getenv("LDAP_PASS")

def ldap_authenticate(username, password):
    """
    Authenticate a user via LDAP or as the static admin user.
    If admin login, validate against the admin database.
    """
    if username == ADMIN_USERNAME:
        return admin_login(username, password)

    try:
        user_dn = f"{LDAP_DOMAIN}\\{username}"
        server = Server(LDAP_SERVER, get_info=ALL, use_ssl=True)
        conn = Connection(server, user=user_dn, password=password, authentication=NTLM, auto_bind=True)
        conn.unbind()
        return True
    except Exception as e:
        logger.error(f"LDAP authentication failed for user {username}: {e}")
        return False
    
def search_ldap_users(query, page_size=500):
    """
    Search LDAP for users matching the query with pagination.
    """
    try:
        # Base DN for LDAP search
        LDAP_BASE_DN = f"DC={LDAP_DOMAIN.replace('.', ',DC=')}"

        # Connect to the LDAP server
        server = Server(LDAP_SERVER, get_info=ALL, use_ssl=True)
        conn = Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True)
        logger.info("LDAP connection successful")
        logger.info(f"LDAP search query: {query}")

        # Define search filter and attributes
        search_filter = f"(|(sAMAccountName=*{query}*)(mail=*{query}*))"
        attributes = ['name', 'sAMAccountName', 'distinguishedName', 'mail']

        # Initialize results and pagination variables
        total_entries = []
        entry_count = 0
        cookie = None

        # Perform paged search
        while True:
            conn.search(
                search_base=LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=page_size,
                paged_cookie=cookie
            )

            results = []
            for entry in conn.entries:
                entry_count += 1
                logger.debug(f"Processing entry {entry_count}")
                results.append({
                    "username": str(entry.sAMAccountName.value) if entry.sAMAccountName else None,
                    "email": str(entry.mail.value) if entry.mail else None,
                    "full_name": str(entry.name.value) if entry.name else None,
                    "distinguished_name": str(entry.distinguishedName.value) if entry.distinguishedName else None
                })

            total_entries.extend(results)
            logger.info(f"Retrieved {len(results)} entries in the current page")

            # Retrieve the cookie for the next page
            cookie = conn.result.get('controls', {}).get('1.2.840.113556.1.4.319', {}).get('value', {}).get('cookie')
            if not cookie:
                break

        logger.info(f"Total entries retrieved: {len(total_entries)}")
        conn.unbind()
        return total_entries

    except Exception as e:
        logger.error(f"Error searching LDAP: {e}")
        raise RuntimeError(f"LDAP search failed: {e}")


def login_required_json(f):
    """
    Decorator for protecting JSON routes (API endpoints).
    Returns 401 in JSON if not logged in.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            logger.warning("Unauthorized access attempt to JSON route")
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


def login_required_html(f):
    """
    Decorator for protecting routes that serve HTML (like serving the main React index).
    Redirects to a login page if not authenticated.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            logger.warning("Unauthorized access attempt to HTML route")
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper