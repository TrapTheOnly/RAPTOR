from flask import request, jsonify
from pydantic import ValidationError


def validate_json(schema_cls):
    """
    Parse and validate a JSON body against the given Pydantic schema.
    Returns (data, error_response) where only one is non-None.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return None, (jsonify({"error": "Invalid or missing JSON body"}), 400)
    try:
        data = schema_cls.model_validate(payload)
        return data, None
    except ValidationError as e:
        return None, (jsonify({"error": "Invalid request data", "details": e.errors()}), 400)
