from flask import Flask

from app.services.offsec import (
    add_pentest_collaborator,
    create_checklist_template,
    create_or_update_pentest_data,
    create_report_template,
    delete_checklist_template,
    delete_generated_report_route,
    delete_pentest_data,
    delete_report_route,
    delete_report_template,
    generate_report,
    get_checklist_templates,
    get_pentest_collaborators,
    get_generated_report,
    get_pentest_data,
    get_pentest_record,
    get_pentest_image,
    get_pentest_users,
    get_report,
    get_report_templates,
    reset_checklist_template_to_canonical,
    reset_report_template_to_canonical,
    remove_pentest_collaborator,
    update_checklist_template,
    update_report_template,
    upload_report_template_logo,
    upload_pentest_image,
)


def register_offsec_routes(app: Flask) -> None:
    app.add_url_rule("/pentest/<int:record_id>", methods=["POST"], view_func=create_or_update_pentest_data)
    app.add_url_rule("/pentest/records", methods=["GET"], view_func=get_pentest_data)
    app.add_url_rule("/pentest/<int:record_id>", methods=["GET"], view_func=get_pentest_record)
    app.add_url_rule("/pentest/<int:record_id>", methods=["DELETE"], view_func=delete_pentest_data)
    app.add_url_rule("/pentest/<int:record_id>/report", methods=["GET"], view_func=get_report)
    app.add_url_rule("/pentest/<int:record_id>/report", methods=["DELETE"], view_func=delete_report_route)
    app.add_url_rule("/pentest/<int:record_id>/generate-report", methods=["POST"], view_func=generate_report)
    app.add_url_rule("/pentest/<int:record_id>/generated-report", methods=["GET"], view_func=get_generated_report)
    app.add_url_rule(
        "/pentest/<int:record_id>/generated-report",
        methods=["DELETE"],
        view_func=delete_generated_report_route,
    )
    app.add_url_rule("/pentest_users", methods=["GET"], view_func=get_pentest_users)
    app.add_url_rule("/pentest/<int:record_id>/images", methods=["POST"], view_func=upload_pentest_image)
    app.add_url_rule("/pentest/images/<string:filename>", methods=["GET"], view_func=get_pentest_image)
    app.add_url_rule(
        "/pentest/<int:record_id>/collaborators",
        methods=["GET"],
        view_func=get_pentest_collaborators,
    )
    app.add_url_rule(
        "/pentest/<int:record_id>/collaborators",
        methods=["POST"],
        view_func=add_pentest_collaborator,
    )
    app.add_url_rule(
        "/pentest/<int:record_id>/collaborators/<string:username>",
        methods=["DELETE"],
        view_func=remove_pentest_collaborator,
    )
    app.add_url_rule("/checklist-templates", methods=["GET"], view_func=get_checklist_templates)
    app.add_url_rule("/checklist-templates", methods=["POST"], view_func=create_checklist_template)
    app.add_url_rule(
        "/checklist-templates/<int:template_id>",
        methods=["PUT"],
        view_func=update_checklist_template,
    )
    app.add_url_rule(
        "/checklist-templates/<int:template_id>",
        methods=["DELETE"],
        view_func=delete_checklist_template,
    )
    app.add_url_rule(
        "/checklist-templates/<int:template_id>/reset",
        methods=["POST"],
        view_func=reset_checklist_template_to_canonical,
    )
    app.add_url_rule("/report-templates", methods=["GET"], view_func=get_report_templates)
    app.add_url_rule("/report-templates", methods=["POST"], view_func=create_report_template)
    app.add_url_rule("/report-templates/logo-upload", methods=["POST"], view_func=upload_report_template_logo)
    app.add_url_rule(
        "/report-templates/<int:template_id>",
        methods=["PUT"],
        view_func=update_report_template,
    )
    app.add_url_rule(
        "/report-templates/<int:template_id>",
        methods=["DELETE"],
        view_func=delete_report_template,
    )
    app.add_url_rule(
        "/report-templates/<int:template_id>/reset",
        methods=["POST"],
        view_func=reset_report_template_to_canonical,
    )
