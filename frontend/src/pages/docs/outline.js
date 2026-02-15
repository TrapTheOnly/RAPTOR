const GETTING_STARTED_ARTICLES = {
  'platform-overview': {
    warning: {
      variant: 'important',
      title: 'IMPORTANT',
      paragraphs: [
        'This page documents the current RAPTOR interface contract. Validate your deployed version before changing operational procedures.'
      ]
    },
    sections: [
      {
        id: 'scope-and-intent',
        title: 'Scope and intent',
        paragraphs: [
          'RAPTOR is an operational workspace for internet-facing inventory and security testing execution. It joins record metadata, pentest state, and management analytics in one workflow model.',
          'The platform is built for continuous operations. It favors deterministic routing, permission-aware visibility, and stable object links so teams can move quickly without losing context.'
        ]
      },
      {
        id: 'operational-domains',
        title: 'Operational domains',
        paragraphs: [
          'RAPTOR is partitioned into four domains. Each domain is responsible for a distinct operational outcome.'
        ],
        table: {
          columns: ['Domain', 'Primary responsibility', 'Core objects', 'Operational output'],
          rows: [
            ['Records', 'Maintain internet-facing asset metadata and ownership.', 'Record, application, owner, maintainer, open ports.', 'Reliable inventory and accountability.'],
            ['Security', 'Manage test assignment and lifecycle progression.', 'Pentest record, assignee, status, vulnerability indicators.', 'Current risk and remediation posture.'],
            ['Dashboard', 'Aggregate posture and throughput signals.', 'KPI summaries, trend series, activity history.', 'Prioritization input for leadership and ops.'],
            ['Settings', 'Control users, taxonomy, templates, and policy controls.', 'Roles, permissions, categories, templates.', 'Governed and consistent platform behavior.']
          ]
        }
      },
      {
        id: 'core-data-model',
        title: 'Core data model',
        paragraphs: [
          'RAPTOR uses linked operational entities. Applications group records by service boundary. Records hold technical and ownership metadata. Pentest records hold test execution state for each record.',
          'Most reporting and dashboard views are derived from this relationship model, so metadata integrity directly affects decision quality.'
        ],
        table: {
          columns: ['Entity', 'Meaning', 'Critical fields'],
          rows: [
            ['Application', 'Logical product or service grouping context.', '`name`'],
            ['Record', 'Internet-facing DNS asset with operational metadata.', '`domain`, `source`, `application_id`, `application_owner`, `maintainer`, `open_ports`'],
            ['Pentest record', 'Security workflow state linked to a record.', '`status`, `tested_by`, `test_start_date`, `test_end_date`, `vulnerable`, `vulnerability_fixed`']
          ]
        }
      },
      {
        id: 'execution-baseline',
        title: 'Execution baseline',
        paragraphs: [
          'A stable weekly cycle keeps RAPTOR data useful. Teams should keep record metadata current, track security ownership explicitly, and close workflows only when report and remediation linkage is complete.'
        ],
        orderedList: [
          'Review and correct inventory data in `Records`.',
          'Assign pentest ownership and active scope in `Security`.',
          'Update status transitions as execution progresses.',
          'Attach report and ticket linkage before closure.',
          'Use `Dashboard` trends for planning and escalation.'
        ],
        related: [
          {
            label: 'Record Management: Records Dashboard Overview',
            to: '/docs/records-management/records-dashboard-overview'
          },
          {
            label: 'Pentest Operations: Security Dashboard Overview',
            to: '/docs/pentest-operations/security-dashboard-overview'
          }
        ]
      }
    ]
  },
  'login-and-session-management': {
    warning: {
      variant: 'important',
      title: 'IMPORTANT',
      paragraphs: [
        'RAPTOR performs server-validated session checks during active use. Unsaved edits can be lost when re-authentication is required.'
      ]
    },
    sections: [
      {
        id: 'authentication-contract',
        title: 'Authentication contract',
        paragraphs: [
          'Authentication and authorization are enforced separately. Login establishes identity, while route visibility and action availability are derived from role plus effective permissions.',
          'After login, RAPTOR loads session status and applies capability checks before rendering module navigation and page actions.'
        ]
      },
      {
        id: 'first-access-reset',
        title: 'First access and reset behavior',
        paragraphs: [
          'Some accounts are provisioned with a reset-required state. In this state, RAPTOR routes users through password reset before granting normal navigation.',
          'This prevents partial operational access under transitional credential state.'
        ]
      },
      {
        id: 'session-lifecycle',
        title: 'Session lifecycle',
        paragraphs: [
          'RAPTOR tracks session validity continuously. A warning dialog appears before expiration and offers explicit continuation or logout paths.'
        ],
        table: {
          columns: ['Event', 'Visible behavior', 'System effect'],
          rows: [
            ['Pre-expiry threshold', 'Warning dialog with `Stay logged in (+1h)` and `Log out`.', 'User confirms continuation or session termination.'],
            ['Extension accepted', 'Dialog closes and work continues.', 'Server returns refreshed session timing.'],
            ['Expired session detected', 'User is redirected to login.', 'Local auth state is cleared.']
          ]
        }
      },
      {
        id: 'logout-semantics',
        title: 'Logout semantics',
        paragraphs: [
          'Logout requests server-side session termination and always clears client-side auth state. Even when network failure occurs, local state is invalidated as a safety fallback.'
        ]
      },
      {
        id: 'troubleshooting-pattern',
        title: 'Troubleshooting pattern',
        paragraphs: [
          'Most access issues are caused by expired sessions, missing permissions, or reset-required account state. Validate these conditions first before deeper diagnostics.'
        ],
        table: {
          columns: ['Symptom', 'Likely cause', 'First check'],
          rows: [
            ['Repeated redirect to login', 'Session expiration or cookie policy mismatch.', 'Re-authenticate and validate browser cookie settings.'],
            ['Missing module tab', 'Permission not granted to current account.', 'Compare role and optional permissions with expected profile.'],
            ['Forced reset flow appears', 'Account flagged as reset required.', 'Complete reset flow or confirm user policy with admin.']
          ]
        }
      }
    ]
  },
  'navigation-model': {
    sections: [
      {
        id: 'header-navigation',
        title: 'Header navigation behavior',
        paragraphs: [
          'The global header is the primary module switch. It only displays modules that the current session can open. This eliminates dead-end navigation and supports least-privilege operation.',
          'The RAPTOR logo returns users to their role default route, which acts as a stable recovery point in deep workflows.'
        ]
      },
      {
        id: 'route-map',
        title: 'Route map',
        paragraphs: [
          'Route contracts are stable and should be used for operational handoff links.'
        ],
        table: {
          columns: ['Route', 'Purpose', 'Permission gate'],
          rows: [
            ['`/dashboard`', 'Operational and executive analytics.', '`view_dashboard`'],
            ['`/records`', 'Inventory and metadata operations.', '`view_records`'],
            ['`/records/record/:recordId`', 'Detailed record history view.', '`view_record_details`'],
            ['`/pentest`', 'Security execution board.', '`view_security_dashboard`'],
            ['`/pentest/record/:recordId`', 'Detailed pentest execution page.', '`view_pentest_page`'],
            ['`/settings`', 'Configuration and governance controls.', '`view_settings`'],
            ['`/docs/:sectionSlug/:pageSlug`', 'Documentation pages.', 'Logged-in session']
          ]
        }
      },
      {
        id: 'deep-link-handoffs',
        title: 'Deep links and handoffs',
        paragraphs: [
          'Use deep links for reviews, triage, and cross-team handoffs. A direct object route reduces ambiguity and preserves context during escalation and QA loops.'
        ]
      },
      {
        id: 'navigation-safety',
        title: 'Navigation safety during edits',
        paragraphs: [
          'Complete save operations before switching routes. Session revalidation can force redirects and interrupt unsaved forms.',
          'Avoid editing the same record in multiple tabs under the same account. Parallel tab state is a common source of stale edits.'
        ],
        tip: {
          variant: 'tip',
          title: 'TIP',
          paragraphs: [
            'For operational reviews, start from `Dashboard` and drill into `Records` or `Security` only when a KPI requires root-cause analysis.'
          ]
        }
      }
    ]
  },
  'roles-and-capability-matrix': {
    sections: [
      {
        id: 'authorization-model',
        title: 'Authorization model',
        paragraphs: [
          'RAPTOR combines role defaults with optional permission extensions. This preserves predictable baseline behavior while allowing targeted capability expansion when required.'
        ]
      },
      {
        id: 'role-matrix',
        title: 'Role matrix',
        table: {
          columns: ['Role', 'Default route', 'Operational emphasis', 'Capability profile'],
          rows: [
            ['admin', '`/dashboard`', 'Governance and full-system administration.', 'Full access including sensitive controls.'],
            ['manager', '`/dashboard`', 'Coverage, throughput, and team coordination.', 'Broad access across dashboard, records, security, and settings.'],
            ['pentester', '`/pentest`', 'Test execution and finding progression.', 'Security workflow actions plus pentest export.'],
            ['user', '`/records`', 'Inventory quality and metadata upkeep.', 'Record visibility and controlled record updates.']
          ]
        }
      },
      {
        id: 'capability-evaluation',
        title: 'Capability evaluation order',
        paragraphs: [
          'Effective permissions are computed in a fixed order to keep frontend and backend authorization behavior consistent.'
        ],
        orderedList: [
          'Load role default permissions.',
          'Merge valid optional permissions.',
          'Apply admin full-access behavior when role is `admin`.',
          'Evaluate route and action checks against merged capability set.'
        ]
      },
      {
        id: 'access-governance',
        title: 'Access governance',
        paragraphs: [
          'Use least-privilege defaults and grant additional permissions only for clear operational need. Review elevated permissions periodically and remove stale grants.'
        ],
        list: [
          'Prefer targeted optional grants over broad role changes.',
          'Document why sensitive permissions were granted.',
          'Review elevated access on a regular cadence.'
        ],
        related: [
          {
            label: 'Operations and Governance: Permissions Reference',
            to: '/docs/operations-and-governance/permissions-reference'
          }
        ]
      }
    ]
  }
};

export const DOC_SECTIONS = [
  {
    slug: 'getting-started',
    title: 'Getting Started',
    description: 'Essential setup and navigation fundamentals for all users.',
    pages: [
      {
        slug: 'platform-overview',
        title: 'Platform Overview',
        audience: ['All users'],
        summary: 'Defines RAPTOR scope, module boundaries, and the baseline operating model.',
        coverage: [
          'Platform scope and intended usage model',
          'Operational domains and outputs',
          'Core entities and ownership expectations',
          'Execution baseline and data quality standards'
        ],
        article: GETTING_STARTED_ARTICLES['platform-overview']
      },
      {
        slug: 'login-and-session-management',
        title: 'Login and Session Management',
        audience: ['All users', 'Admins'],
        summary:
          'Explains authentication, role-driven access, session behavior, and practical troubleshooting.',
        coverage: [
          'Authentication and capability loading',
          'Password reset required flow',
          'Session warning and expiry behavior',
          'Operational access troubleshooting baseline'
        ],
        article: GETTING_STARTED_ARTICLES['login-and-session-management']
      },
      {
        slug: 'navigation-model',
        title: 'Navigation Model',
        audience: ['All users'],
        summary:
          'Documents route behavior, permission-driven visibility, and safe navigation patterns.',
        coverage: [
          'Header navigation contract',
          'Route map and permission gates',
          'Deep-link operational handoff practices',
          'Editing safety while navigating'
        ],
        article: GETTING_STARTED_ARTICLES['navigation-model']
      },
      {
        slug: 'roles-and-capability-matrix',
        title: 'Roles and Capability Matrix',
        audience: ['All users', 'Admins'],
        summary:
          'Details role defaults, optional permission extensions, and capability evaluation order.',
        coverage: [
          'Role-level operational emphasis',
          'Permission extension model',
          'Effective capability evaluation order',
          'Governance approach for access control'
        ],
        article: GETTING_STARTED_ARTICLES['roles-and-capability-matrix']
      }
    ]
  },
  {
    slug: 'records-management',
    title: 'Record Management',
    description: 'Lifecycle operations for DNS/app records and ownership metadata.',
    pages: [
      {
        slug: 'records-dashboard-overview',
        title: 'Records Dashboard Overview',
        audience: ['Users', 'Managers', 'Admins'],
        summary: 'Covers the record inventory view, list modes, and operational status indicators.',
        coverage: [
          'Record grouping by application',
          'Record card fields and status signals',
          'Data freshness and sort logic',
          'When to use grouped vs flat list view'
        ]
      },
      {
        slug: 'record-lifecycle-and-editing',
        title: 'Record Lifecycle and Editing',
        audience: ['Users', 'Managers', 'Admins'],
        summary:
          'Defines how records are edited, validated, and maintained over time, including destructive actions.',
        coverage: [
          'Edit mode behavior and save/cancel flows',
          'Open ports, maintainer, owner, and application fields',
          'Deletion flow and safeguards',
          'History and record detail drill-down'
        ]
      },
      {
        slug: 'application-management',
        title: 'Application Management',
        audience: ['Managers', 'Admins'],
        summary:
          'Explains app grouping, create/rename/delete operations, and how ownership context is applied.',
        coverage: [
          'Manage Apps dialog workflow',
          'Assigning records to applications',
          'Meaning of application owner vs maintainer',
          'Impact of app rename/delete on assigned records'
        ]
      },
      {
        slug: 'search-filter-and-export-records',
        title: 'Search, Filter, and Export',
        audience: ['Users', 'Managers', 'Admins'],
        summary:
          'Teaches query-assisted filtering, parameter search patterns, and CSV export expectations.',
        coverage: [
          'Filter chips and parameterized search syntax',
          'Suggestion behavior and keyboard flow',
          'Combining filters with free-text search',
          'CSV export scope and expected output columns'
        ]
      }
    ]
  },
  {
    slug: 'pentest-operations',
    title: 'Pentest Operations',
    description: 'Operational guide for pentest assignment, execution, findings, and closure.',
    pages: [
      {
        slug: 'security-dashboard-overview',
        title: 'Security Dashboard Overview',
        audience: ['Pentesters', 'Managers', 'Admins'],
        summary:
          'Explains pentest board organization, status dimensions, and high-level workflow states.',
        coverage: [
          'Pentest card model and status lifecycle',
          'Risk-focused filters and grouping controls',
          'Assignment indicators and unassigned queues',
          'Data sources for pentest summary metrics'
        ]
      },
      {
        slug: 'pentest-record-lifecycle',
        title: 'Pentest Record Lifecycle',
        audience: ['Pentesters', 'Managers', 'Admins'],
        summary:
          'Documents end-to-end pentest execution from assignment to completion and remediation status.',
        coverage: [
          'Start/in-progress/completed transitions',
          'Date fields and lifecycle consistency checks',
          'Service desk linking and report state',
          'When to reopen or close a security test'
        ]
      },
      {
        slug: 'findings-and-checklist-management',
        title: 'Findings and Checklist Management',
        audience: ['Pentesters', 'Managers'],
        summary:
          'Defines checklist usage, findings curation, markdown quality standards, and evidence hygiene.',
        coverage: [
          'Checklist execution and result recording',
          'Finding severity and vulnerability flags',
          'Markdown conventions for reproducibility',
          'Quality controls before final report export'
        ]
      },
      {
        slug: 'assignment-and-reassignment',
        title: 'Assignment and Reassignment',
        audience: ['Pentesters', 'Managers', 'Admins'],
        summary:
          'Explains assign-to-me, admin reassignment, and controlled edits to other tester records.',
        coverage: [
          'Permission-based assignment controls',
          'Admin override and reassign behavior',
          'Ownership expectations and handoff rules',
          'Avoiding workflow collisions during parallel edits'
        ]
      }
    ]
  },
  {
    slug: 'dashboards-and-analytics',
    title: 'Dashboards and Analytics',
    description: 'Definition reference for KPIs, charts, trends, and prioritization views.',
    pages: [
      {
        slug: 'executive-dashboard',
        title: 'Executive Dashboard',
        audience: ['Managers', 'Admins'],
        summary:
          'Introduces KPI cards and executive-level security posture summaries across tracked assets.',
        coverage: [
          'KPI intent and update cadence',
          'Coverage, throughput, and open-risk metrics',
          'Recent activity and workload summaries',
          'How managers should interpret trend changes'
        ]
      },
      {
        slug: 'chart-and-kpi-definitions',
        title: 'Chart and KPI Definitions',
        audience: ['Managers', 'Admins', 'Pentesters'],
        summary:
          'Provides precise definitions, formulas, and caveats for each dashboard statistic and chart.',
        coverage: [
          'Metric formulas and denominator rules',
          'Trend windows and aggregation logic',
          'Data quality dependencies and staleness effects',
          'Examples for common interpretation mistakes'
        ]
      },
      {
        slug: 'risk-and-prioritization-workflows',
        title: 'Risk and Prioritization Workflows',
        audience: ['Managers', 'Admins', 'Pentesters'],
        summary:
          'Covers how to use analytics for prioritizing tests, remediation, and stakeholder reporting.',
        coverage: [
          'Top-risk asset triage process',
          'Backlog balancing across testers',
          'Remediation verification priorities',
          'Operational review cadences'
        ]
      },
      {
        slug: 'activity-timelines-and-audit-signals',
        title: 'Activity Timelines and Audit Signals',
        audience: ['Managers', 'Admins'],
        summary:
          'Describes change indicators and timeline signals used for audit preparation and governance checks.',
        coverage: [
          'Recent activity feed semantics',
          'Detecting stalled records and overdue tests',
          'Using history views for governance evidence',
          'Escalation triggers and operational thresholds'
        ]
      }
    ]
  },
  {
    slug: 'reporting',
    title: 'Reporting',
    description: 'Template-driven reporting and evidence packaging for stakeholders.',
    pages: [
      {
        slug: 'report-generation-flow',
        title: 'Report Generation Flow',
        audience: ['Pentesters', 'Managers', 'Admins'],
        summary:
          'Maps the report lifecycle from draft content to final PDF attachment and delivery readiness.',
        coverage: [
          'Required inputs and pre-export checks',
          'How findings, checklists, and metadata become report content',
          'Draft/replace/delete report behavior',
          'Versioning and verification practices'
        ]
      },
      {
        slug: 'report-templates-and-branding',
        title: 'Report Templates and Branding',
        audience: ['Managers', 'Admins'],
        summary:
          'Explains template configuration, live preview usage, and standards alignment for consistent outputs.',
        coverage: [
          'Template sections and variable placeholders',
          'Live preview behavior and validation',
          'Branding and document consistency controls',
          'Template governance and change approval'
        ]
      },
      {
        slug: 'distribution-and-sharing-controls',
        title: 'Distribution and Sharing Controls',
        audience: ['Managers', 'Admins'],
        summary:
          'Documents report distribution expectations, data handling rules, and cross-team handoff patterns.',
        coverage: [
          'Internal vs external sharing considerations',
          'Service desk linkage and tracking completeness',
          'Data sensitivity handling for exported reports',
          'Operational checklist before stakeholder sendout'
        ]
      }
    ]
  },
  {
    slug: 'administration',
    title: 'Administration',
    description: 'Complete map of admin settings, controls, and maintenance responsibilities.',
    pages: [
      {
        slug: 'admin-settings-map',
        title: 'Admin Settings Map',
        audience: ['Admins', 'Managers'],
        summary:
          'Provides a full index of settings panels and what each control changes in system behavior.',
        coverage: [
          'Settings navigation and section purpose',
          'Safe order for initial configuration',
          'Dependencies between settings groups',
          'Rollback and change verification approach'
        ]
      },
      {
        slug: 'user-management-and-authentication',
        title: 'User Management and Authentication',
        audience: ['Admins'],
        summary:
          'Covers local/domain user flows, role assignment, auth modes, and account lifecycle operations.',
        coverage: [
          'Create, edit, disable, and reset user access',
          'Domain user onboarding and sync considerations',
          'Auth type behavior and constraints',
          'Role assignment governance'
        ]
      },
      {
        slug: 'security-controls-and-maintenance',
        title: 'Security Controls and Maintenance',
        audience: ['Admins'],
        summary:
          'Explains maintenance mode, platform security controls, and sensitive administrative actions.',
        coverage: [
          'Maintenance toggles and operational effect',
          'Security hardening controls and defaults',
          'Reset pentest data safeguards',
          'Admin-only emergency procedures'
        ]
      },
      {
        slug: 'customization-and-taxonomies',
        title: 'Customization and Taxonomies',
        audience: ['Admins', 'Managers'],
        summary:
          'Documents IP source management, vulnerability category setup, and checklist/template customization.',
        coverage: [
          'Managing IP source groups and scope',
          'Vulnerability category taxonomy design',
          'Checklist template governance',
          'Keeping taxonomy aligned with reporting outputs'
        ]
      }
    ]
  },
  {
    slug: 'operations-and-governance',
    title: 'Operations and Governance',
    description: 'Runbook guidance for reliability, audits, and long-term platform operation.',
    pages: [
      {
        slug: 'permissions-reference',
        title: 'Permissions Reference',
        audience: ['Admins', 'Managers'],
        summary:
          'Single reference for permission keys, effective access behavior, and role fallback logic.',
        coverage: [
          'Permission catalog and practical meaning',
          'Role defaults vs explicit grants',
          'How permission checks impact UI and APIs',
          'Troubleshooting missing capability'
        ]
      },
      {
        slug: 'audit-and-troubleshooting',
        title: 'Audit and Troubleshooting',
        audience: ['Admins', 'Managers'],
        summary:
          'Provides methods to investigate anomalies, verify data health, and resolve common operational issues.',
        coverage: [
          'First-response troubleshooting flow',
          'Detecting inconsistent records or test states',
          'Session and access issue triage',
          'Audit evidence checklist'
        ]
      },
      {
        slug: 'data-retention-and-backup',
        title: 'Data Retention and Backup',
        audience: ['Admins'],
        summary:
          'Defines retention considerations for records, findings, reports, and supporting evidence data.',
        coverage: [
          'Retention policy decision points',
          'Backup scope and restore strategy',
          'Data integrity checks after restore',
          'Controlled cleanup and archival guidance'
        ]
      },
      {
        slug: 'onboarding-and-rollout-playbook',
        title: 'Onboarding and Rollout Playbook',
        audience: ['Admins', 'Managers'],
        summary:
          'Operational rollout guide for launching RAPTOR to new teams and scaling usage safely.',
        coverage: [
          'Pilot rollout sequence',
          'Training path by role',
          'Baseline configuration checklist',
          'Steady-state review and improvement loop'
        ]
      }
    ]
  }
];

export const DEFAULT_DOC_ROUTE = {
  sectionSlug: DOC_SECTIONS[0].slug,
  pageSlug: DOC_SECTIONS[0].pages[0].slug
};

export const flattenDocsPages = () =>
  DOC_SECTIONS.flatMap((section) =>
    section.pages.map((page) => ({
      ...page,
      sectionSlug: section.slug,
      sectionTitle: section.title
    }))
  );
