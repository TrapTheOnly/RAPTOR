import os
import sqlite3
import logging
from flask import Blueprint, jsonify, request, session

from ..services.admin import admin_login
from ..services.auth import ldap_authenticate
from ..config import DB_PATH
from ..schemas import LoginSchema
from ..schemas.utils import validate_json

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate the user and set session variables.
    """
    data, error = validate_json(LoginSchema)
    if error:
        return error

    username = data.username.lower()
    password = data.password

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, role FROM allowed_users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()

    if username == os.getenv("ADMIN_USERNAME"):
        if admin_login(username, password):
            session.permanent = True
            session["logged_in"] = True
            session["username"] = username
            session["user_type"] = "admin"
            return (
                jsonify({"status": "logged_in", "username": username, "user_type": "admin"}),
                200,
            )
        return jsonify({"error": "Invalid credentials"}), 401

    if user:
        if ldap_authenticate(username, password):
            session.permanent = True
            session["logged_in"] = True
            session["username"] = user[0]
            session["user_type"] = user[1] if user[1] else "user"
            return (
                jsonify(
                    {
                        "status": "logged_in",
                        "username": username,
                        "user_type": session["user_type"],
                    }
                ),
                200,
            )
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/session-status", methods=["GET"])
def session_status():
    """
    Check if the user is logged in.
    """
    if "logged_in" in session and session["logged_in"]:
        user_type = session.get("user_type")
        return jsonify({"status": "logged_in", "username": session.get("username"), "user_type": user_type}), 200
    return jsonify({"status": "logged_out"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Clear the session variables and log out the user.
    """
    session.clear()
    return jsonify({"status": "logged_out"}), 200
