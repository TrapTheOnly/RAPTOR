MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 64
COMMON_PASSWORDS = {
    "password",
    "password1",
    "123456",
    "12345678",
    "123456789",
    "qwerty",
    "qwerty123",
    "letmein",
    "welcome",
    "admin",
    "admin123",
    "iloveyou",
    "monkey",
    "dragon",
    "football",
    "abc123",
    "111111",
    "trustno1",
    "sunshine",
    "princess",
    "login",
    "qwertyuiop",
    "passw0rd",
    "master",
    "shadow",
}


def validate_password_nist(password, username=None):
    """Validate password against NIST-style requirements."""
    if not password:
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters."

    lowered = password.strip().lower()
    if lowered in COMMON_PASSWORDS:
        return False, "Password is too common."
    if username and username.lower() in lowered:
        return False, "Password must not contain the username."
    return True, ""


__all__ = [
    "COMMON_PASSWORDS",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "validate_password_nist",
]
