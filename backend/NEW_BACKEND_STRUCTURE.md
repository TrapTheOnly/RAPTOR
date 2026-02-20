# New Backend Structure Responsibilities

| File | Responsibility |
|---|---|
| `backend/app/__init__.py` | Creates and configures the Flask app instance, then registers all routes and integrations. |
| `backend/app/bootstrap/__init__.py` | Initializes the `backend/app/bootstrap` package namespace and package-level exports. |
| `backend/app/bootstrap/db_init.py` | Coordinates schema creation and data seeding during application startup. |
| `backend/app/bootstrap/scheduler.py` | Runs and manages the periodic background update scheduler lifecycle. |
| `backend/app/bootstrap/schema_setup.py` | Creates and migrates database tables/columns required by the app schema. |
| `backend/app/bootstrap/seed_data.py` | Seeds canonical checklist/report template and vulnerability category records. |
| `backend/app/bootstrap/seed_orchestrator.py` | Orchestrates all database seed routines in one startup call. |
| `backend/app/config.py` | Centralizes environment-driven configuration values and logging setup for the backend. |
| `backend/app/domain/__init__.py` | Initializes the `backend/app/domain` package namespace and package-level exports. |
| `backend/app/domain/auth/__init__.py` | Initializes the `backend/app/domain/auth` package namespace and package-level exports. |
| `backend/app/domain/auth/password_policy.py` | Defines password policy constants and validation rules for auth flows. |
| `backend/app/domain/auth/permissions.py` | Defines permission/role matrices and helpers for role-based authorization. |
| `backend/app/domain/catalogs/__init__.py` | Initializes the `backend/app/domain/catalogs` package namespace and package-level exports. |
| `backend/app/domain/catalogs/checklist_catalog.py` | Loads and validates canonical checklist templates from bundled catalog files. |
| `backend/app/domain/catalogs/report_template_catalog.py` | Loads and validates canonical report template definitions from catalog files. |
| `backend/app/domain/docs/__init__.py` | Initializes the `backend/app/domain/docs` package namespace and package-level exports. |
| `backend/app/domain/docs/manifest_schema.py` | Loads docs manifest/content metadata and shared docs-domain constants. |
| `backend/app/domain/offsec/__init__.py` | Initializes the `backend/app/domain/offsec` package namespace and package-level exports. |
| `backend/app/domain/offsec/shared.py` | Provides shared OffSec constants, normalization helpers, and serialization utilities. |
| `backend/app/http/__init__.py` | Initializes the `backend/app/http` package namespace and package-level exports. |
| `backend/app/http/decorators/__init__.py` | Initializes the `backend/app/http/decorators` package namespace and package-level exports. |
| `backend/app/http/decorators/admin_required.py` | Enforces admin/manager session authorization guards on protected endpoints. |
| `backend/app/http/decorators/login_required.py` | Enforces authenticated-session guards for JSON and HTML routes. |
| `backend/app/http/decorators/permission_required.py` | Enforces permission-scoped authorization checks for protected handlers. |
| `backend/app/http/request_utils.py` | Normalizes/validates request payload primitives used by route and service layers. |
| `backend/app/integrations/__init__.py` | Initializes the `backend/app/integrations` package namespace and package-level exports. |
| `backend/app/integrations/db/__init__.py` | Initializes the `backend/app/integrations/db` package namespace and package-level exports. |
| `backend/app/integrations/db/connection.py` | Provides PostgreSQL connection/cursor helpers, placeholder conversion, and column introspection utilities. |
| `backend/app/integrations/ldap/__init__.py` | Initializes the `backend/app/integrations/ldap` package namespace and package-level exports. |
| `backend/app/integrations/ldap/client.py` | Implements LDAP bind authentication and paginated user search operations. |
| `backend/app/integrations/reporting/__init__.py` | Initializes the `backend/app/integrations/reporting` package namespace and package-level exports. |
| `backend/app/integrations/reporting/report_pdf_blocks.py` | Renders template blocks into reportlab story elements for generated PDFs. |
| `backend/app/integrations/reporting/report_pdf_layout.py` | Provides reportlab layout/formatting primitives for PDF rendering. |
| `backend/app/integrations/reporting/report_pdf_model.py` | Builds normalized report data model/context used by PDF templates. |
| `backend/app/integrations/reporting/report_pdf_render.py` | Orchestrates end-to-end PDF rendering from report template definitions. |
| `backend/app/integrations/storage/__init__.py` | Initializes the `backend/app/integrations/storage` package namespace and package-level exports. |
| `backend/app/integrations/storage/offsec_storage.py` | Handles FTP-backed file storage, retrieval, and cleanup for OffSec assets. |
| `backend/app/repositories/__init__.py` | Initializes the `backend/app/repositories` package namespace and package-level exports. |
| `backend/app/repositories/admin_users_repository.py` | Performs admin user persistence and password-hash storage operations. |
| `backend/app/repositories/applications_repository.py` | Performs CRUD queries for application entities. |
| `backend/app/repositories/auth_lockout_repository.py` | Persists login failure counters and lockout state transitions. |
| `backend/app/repositories/ip_sources_repository.py` | Performs CRUD queries for IP source mappings. |
| `backend/app/repositories/offsec/__init__.py` | Initializes the `backend/app/repositories/offsec` package namespace and package-level exports. |
| `backend/app/repositories/offsec/offsec_records.py` | Fetches and enforces OffSec record/pentest access and related data queries. |
| `backend/app/repositories/records_mutation_repository.py` | Applies record write/update/delete mutations and history side effects. |
| `backend/app/repositories/records_query_repository.py` | Fetches record/dashboard/history read models from the database. |
| `backend/app/repositories/records_repository.py` | Provides a compatibility import surface for split record repositories. |
| `backend/app/repositories/records_row_mapper.py` | Houses reusable row mapping and shared SQL snippets for record repositories. |
| `backend/app/repositories/users_repository.py` | Performs allowed-user persistence and lookup queries. |
| `backend/app/repositories/vuln_categories_repository.py` | Performs CRUD queries for vulnerability category records. |
| `backend/app/routes/__init__.py` | Initializes the `backend/app/routes` package namespace and package-level exports. |
| `backend/app/routes/admin.py` | Defines admin HTTP endpoints and delegates logic to admin-focused services. |
| `backend/app/routes/auth.py` | Defines authentication/session HTTP endpoints and delegates auth workflows. |
| `backend/app/routes/docs.py` | Defines documentation API endpoints and delegates docs access logic. |
| `backend/app/routes/frontend.py` | Serves frontend SPA/static entrypoints and login-protected HTML routes. |
| `backend/app/routes/metadata.py` | Defines metadata endpoints (IP sources and vulnerability categories). |
| `backend/app/routes/offsec_routes.py` | Registers OffSec endpoint URL rules and binds them to OffSec handlers. |
| `backend/app/routes/records.py` | Defines records/apps HTTP endpoints and delegates to record services. |
| `backend/app/services/__init__.py` | Initializes the `backend/app/services` package namespace and package-level exports. |
| `backend/app/services/admin_auth_service.py` | Implements admin auth workflows (bootstrap, password change/reset). |
| `backend/app/services/auth_service.py` | Implements login/logout/session flows, lockout handling, and reset flows. |
| `backend/app/services/authorization_service.py` | Computes effective user permissions and permission checks. |
| `backend/app/services/dns_sync_service.py` | Parses zone files and synchronizes DNS-derived records into persistence. |
| `backend/app/services/docs_access_matrix_service.py` | Builds docs access matrix/visibility models across roles and permissions. |
| `backend/app/services/docs_manifest_service.py` | Resolves user-scoped docs manifests and page content access responses. |
| `backend/app/services/metadata_service.py` | Implements business rules for IP-source and vuln-category metadata operations. |
| `backend/app/services/offsec/__init__.py` | Re-exports OffSec service handlers as a stable package-level interface. |
| `backend/app/services/offsec/offsec_generated_reports.py` | Handles generated report creation, retrieval, and deletion workflows. |
| `backend/app/services/offsec/offsec_pentest.py` | Handles pentest record mutation, uploads, and report/image retrieval endpoints. |
| `backend/app/services/offsec/offsec_templates.py` | Handles checklist/report template listing, CRUD, and reset workflows. |
| `backend/app/services/offsec/offsec_users.py` | Serves OffSec pentest-user lookup endpoint behavior. |
| `backend/app/services/offsec_admin_service.py` | Implements admin-only OffSec maintenance/reset operations. |
| `backend/app/services/records_service.py` | Implements record/app business workflows over repository operations. |
| `backend/app/services/session_policy_service.py` | Implements session timeout, activity tracking, and extension logic. |
| `backend/app/services/user_admin_service.py` | Implements user administration workflows and LDAP-assisted user onboarding. |
