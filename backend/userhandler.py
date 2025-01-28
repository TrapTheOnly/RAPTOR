import os
from flask import session, jsonify, redirect
from functools import wraps
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from adminhandler import admin_login

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
LDAP_SERVER = os.getenv("LDAP_SERVER")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")

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
        return False
    
def search_ldap_users(query):
    """
    Search LDAP for users matching the query.
    """
    try:
        ldap_admin_user = os.getenv("LDAP_USER")
        ldap_admin_pass = os.getenv("LDAP_PASS")

        server = Server(LDAP_SERVER)
        conn = Connection(server, user=ldap_admin_user, password=ldap_admin_pass, auto_bind=True)

        search_filter = f"(|(uid=*{query}*)(mail=*{query}*))"
        conn.search(
            search_base=LDAP_DOMAIN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['uid', 'mail']
        )

        results = []
        for entry in conn.entries:
            results.append({
                "username": str(entry.uid),
                "email": str(entry.mail) if entry.mail else None
            })

        conn.unbind()
        return results
    except Exception as e:
        print(f"Error searching LDAP: {e}")
        raise RuntimeError(f"LDAP search failed: {e}")


def login_required_json(f):
    """
    Decorator for protecting JSON routes (API endpoints).
    Returns 401 in JSON if not logged in.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            print("Unauthorized")
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
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper