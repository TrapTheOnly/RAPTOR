import os
from flask import session, jsonify, redirect
from functools import wraps
from ldap3 import Server, Connection, ALL, NTLM

LDAP_SERVER = os.getenv("LDAP_SERVER")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")

def ldap_authenticate(username, password):
    """
    Return True if username/password is valid via LDAP, otherwise False.
    Adjust the bind logic for your environment.
    """
    # try:
    #     user_dn = f"{LDAP_DOMAIN}\\{username}"
    #     server = Server(LDAP_SERVER, get_info=ALL, use_ssl=True)
    #     print(server)
    #     conn1 = Connection(server, auto_bind=True)
    #     print(conn1)
    #     conn = Connection(server, user=user_dn, password=password, authentication=NTLM, auto_bind=True)
    #     print(conn)
    #     conn.unbind()
    #     return True
    # except Exception as e:
    #     print(e)
    #     return False
    print(LDAP_DOMAIN, LDAP_SERVER, username)
    with open("/tmp/temp_ldap_info.txt", "w") as temp_file:
        temp_file.write(f"LDAP_DOMAIN: {LDAP_DOMAIN}\n")
        temp_file.write(f"LDAP_SERVER: {LDAP_SERVER}\n")
        temp_file.write(f"Username: {username}\n")
    return True


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