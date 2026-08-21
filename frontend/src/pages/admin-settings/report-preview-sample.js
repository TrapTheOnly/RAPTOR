const BASE_FINDINGS = [
  {
    id: 'f-crit',
    title: 'Stored XSS on checkout',
    category: 'Cross-Site Scripting',
    description: 'User input is reflected without encoding.',
    impact: 'An unauthenticated visitor can run script in a checkout operator session.',
    evidence: 'Stored payload executes on /checkout/review.',
    remediation: 'Encode output and set a strict CSP on checkout.',
    created_by: 'alice',
    baseScore: 9.1,
    status: 'open',
    occurrences: [
      { dns_name: 'pay.example.com', environment_slug: 'prod', status: 'open' },
      { dns_name: 'pay.stg.example.com', environment_slug: 'stg', status: 'retest' }
    ],
    also_observed: [{ dns_name: 'pay.qa.example.com', environment_slug: 'qa', status: 'open' }]
  },
  {
    id: 'f-high',
    title: 'Missing SPF',
    category: 'Email Security',
    description: 'No SPF record for the production zone.',
    baseScore: 7.4,
    status: 'retest',
    occurrences: [{ dns_name: 'pay.example.com', environment_slug: 'prod', status: 'retest' }],
    also_observed: []
  },
  {
    id: 'f-med',
    title: 'Verbose error pages',
    category: 'Information Disclosure',
    description: 'Stack traces leak framework versions.',
    baseScore: 5.3,
    status: 'fixed',
    occurrences: [{ dns_name: 'pay.stg.example.com', environment_slug: 'stg', status: 'fixed' }],
    also_observed: []
  }
];

const OPEN_LIKE = new Set(['open', 'retest', 'draft']);
const CLOSED = new Set(['fixed', 'accepted', 'not_affected']);

const computeMetrics = (findings, hostCount) => {
  const severity = { critical: 0, high: 0, medium: 0, low: 0 };
  const occurrence = {
    open: 0,
    retest: 0,
    draft: 0,
    fixed: 0,
    accepted: 0,
    not_affected: 0
  };
  findings.forEach((finding) => {
    const score = Number(finding.baseScore || 0);
    if (score >= 9) severity.critical += 1;
    else if (score >= 7) severity.high += 1;
    else if (score >= 4) severity.medium += 1;
    else severity.low += 1;
    (finding.occurrences || []).forEach((item) => {
      const status = String(item.status || 'open');
      if (occurrence[status] != null) occurrence[status] += 1;
    });
  });
  const openLike = ['open', 'retest', 'draft'].reduce((sum, key) => sum + occurrence[key], 0);
  return {
    vulnerability_count: findings.length,
    critical_count: severity.critical,
    high_count: severity.high,
    medium_count: severity.medium,
    low_count: severity.low,
    critical_high_count: severity.critical + severity.high,
    open_like_count: openLike,
    occurrence_fixed: occurrence.fixed,
    occurrence_open: occurrence.open,
    occurrence_retest: occurrence.retest,
    host_count: hostCount,
    checklist_percentage: 0,
    severity,
    occurrence
  };
};

export const PREVIEW_SCOPE_OPTIONS = [
  { value: 'host', label: 'Host' },
  { value: 'env', label: 'Environment' },
  { value: 'wave', label: 'Wave' },
  { value: 'owner_delivery', label: 'Owner delivery' },
  { value: 'wave_archive', label: 'Wave archive' },
  { value: 'retest_pack', label: 'Retest pack' },
  { value: 'internal_draft', label: 'Internal draft' }
];

export const sampleReportContext = (kind = 'owner_delivery') => {
  const key = String(kind || 'owner_delivery');
  let findings = BASE_FINDINGS.map((item) => ({
    ...item,
    occurrences: item.occurrences.map((occ) => ({ ...occ })),
    also_observed: (item.also_observed || []).map((occ) => ({ ...occ }))
  }));
  if (key === 'retest_pack') {
    findings = findings.filter((item) =>
      (item.occurrences || []).some((occ) => OPEN_LIKE.has(occ.status) && !CLOSED.has(occ.status))
    );
  }
  const metrics = computeMetrics(findings, key === 'host' ? 1 : 2);
  let scope = 'application';
  let packageKey = 'owner_delivery';
  if (key === 'host') {
    scope = 'host';
    packageKey = 'host';
  } else if (key === 'env') {
    scope = 'environment';
    packageKey = 'owner_delivery';
  } else if (key === 'wave') {
    scope = 'wave';
    packageKey = 'owner_delivery';
  } else if (key === 'wave_archive') {
    scope = 'wave';
    packageKey = 'wave_archive';
  } else if (['owner_delivery', 'retest_pack', 'internal_draft'].includes(key)) {
    packageKey = key;
    scope = 'application';
  }
  const watermark = ['owner_delivery', 'host'].includes(packageKey) ? 'PRODUCTION' : 'NON-PROD';
  const wave =
    scope === 'wave' || packageKey === 'wave_archive'
      ? { id: 4, name: 'Q1 production wave' }
      : { id: '', name: '' };

  if (scope === 'host') {
    return {
      scope,
      package: packageKey,
      application: { id: 12, name: 'Payments Platform' },
      record: {
        name: 'payments.example.com',
        ip_address: '10.20.10.15',
        source: 'Cloud',
        application_name: 'Payments Platform',
        description: 'Customer checkout edge.'
      },
      pentest: {
        status: 'In Progress',
        tested_by: 'senior.pentester, alice',
        test_start_date: '2026-02-01',
        test_end_date: '2026-02-18',
        open_ports: '22, 443, 587'
      },
      wave,
      environments: [{ id: 1, slug: 'prod', is_production: true }],
      hosts: [{ record_id: 9, dns: 'payments.example.com', ip: '10.20.10.15', env: 'prod', ports: [22, 443, 587] }],
      findings,
      metrics,
      open_ports: [22, 443, 587],
      export: {
        id: 'sample',
        watermark: '',
        content_hash: 'abc123',
        signature: 'def456',
        generated_at: '10 February 2026'
      },
      generated_at: '10 February 2026',
      generated_date: '10 February 2026',
      generated_by: 'senior.pentester'
    };
  }

  return {
    scope,
    package: packageKey,
    application: { id: 12, name: 'Payments Platform' },
    record: {
      name: 'Payments Platform',
      ip_address: '',
      source: '',
      application_name: 'Payments Platform',
      description: ''
    },
    pentest: {
      status: 'In Progress',
      tested_by: 'senior.pentester, alice',
      test_start_date: '2026-02-01',
      test_end_date: '2026-02-18',
      open_ports: ''
    },
    wave,
    environments: [
      { id: 1, slug: 'prod', is_production: true },
      { id: 2, slug: 'stg', is_production: false }
    ],
    hosts: [
      { record_id: 9, dns: 'pay.example.com', ip: '', env: 'prod', ports: [] },
      { record_id: 10, dns: 'pay.stg.example.com', ip: '', env: 'stg', ports: [] }
    ],
    findings,
    metrics,
    open_ports: [],
    export: {
      id: 'sample',
      watermark,
      content_hash: 'abc123def',
      signature: 'signedhash',
      generated_at: '10 February 2026'
    },
    generated_at: '10 February 2026',
    generated_date: '10 February 2026',
    generated_by: 'senior.pentester'
  };
};

export const flattenContext = (value, prefix = '', output = {}) => {
  if (Array.isArray(value)) {
    value.forEach((entry, index) => flattenContext(entry, prefix ? `${prefix}.${index}` : `${index}`, output));
    return output;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, entry]) => {
      flattenContext(entry, prefix ? `${prefix}.${key}` : key, output);
    });
    return output;
  }
  output[prefix] = value == null ? '' : String(value);
  return output;
};

export const resolvePreviewText = (text, flat) =>
  String(text || '').replace(/\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g, (_, path) => {
    if (Object.prototype.hasOwnProperty.call(flat, path)) return String(flat[path] ?? '');
    return '';
  });
