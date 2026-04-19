import logging
from typing import Any, Dict, Tuple

from app.integrations.db.connection import IntegrityError
from app.repositories import ip_sources_repository, vuln_categories_repository

logger = logging.getLogger(__name__)


def get_ip_sources() -> Tuple[Dict[str, Any], int]:
    try:
        ip_sources = ip_sources_repository.fetch_ip_sources()
        return {"ip_sources": ip_sources}, 200
    except Exception as e:
        logger.error(f"Error retrieving IP sources: {e}")
        return {"error": "Failed to retrieve IP sources."}, 500


def add_ip_source(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    source_name = str(data.get("source_name") or "").strip()
    ip_address = str(data.get("ip_address") or "").strip()

    if not source_name or not ip_address:
        return {"error": "source_name and ip_address are required."}, 400

    try:
        updated_count = ip_sources_repository.add_ip_source(source_name, ip_address)
        message = (
            f"IP source {ip_address} added as '{source_name}'. "
            f"{updated_count} existing record(s) updated."
        )
        logger.info(message)
        return {"message": message}, 200
    except IntegrityError:
        return {"error": f"IP address {ip_address} is already defined."}, 400
    except Exception as e:
        logger.error(f"Error adding IP source: {e}")
        return {"error": "Failed to add IP source."}, 500


def delete_ip_source(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    ip_address = str(data.get("ip_address") or "").strip()
    if not ip_address:
        return {"error": "ip_address is required."}, 400

    try:
        deleted = ip_sources_repository.delete_ip_source(ip_address)
        if not deleted:
            return {"error": f"No mapping found for IP {ip_address}."}, 404

        source_name, updated_count = deleted
        message = (
            f"IP source mapping for {ip_address} ('{source_name}') deleted. "
            f"{updated_count} record(s) reverted to 'Other'."
        )
        logger.info(message)
        return {"message": message}, 200
    except Exception as e:
        logger.error(f"Error deleting IP source for {ip_address}: {e}")
        return {"error": "Failed to delete IP source."}, 500


def get_vuln_categories() -> Tuple[Dict[str, Any], int]:
    try:
        categories = vuln_categories_repository.fetch_vuln_categories()
        return {"categories": categories}, 200
    except Exception as e:
        logger.error(f"Error fetching vulnerability categories: {e}")
        return {"error": "Failed to fetch categories."}, 500


def add_vuln_category(data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Category name is required."}, 400

    try:
        category_id = vuln_categories_repository.add_vuln_category(name, username)
        return {
            "message": "Category added successfully.",
            "id": category_id,
            "name": name,
        }, 200
    except IntegrityError:
        return {"error": "Category already exists."}, 400
    except Exception as e:
        logger.error(f"Error adding vulnerability category: {e}")
        return {"error": "Failed to add category."}, 500


def delete_vuln_category(category_id: int) -> Tuple[Dict[str, Any], int]:
    try:
        deleted = vuln_categories_repository.delete_vuln_category(category_id)
        if not deleted:
            return {"error": "Category not found."}, 404
        return {"message": "Category deleted successfully."}, 200
    except Exception as e:
        logger.error(f"Error deleting vulnerability category: {e}")
        return {"error": "Failed to delete category."}, 500
