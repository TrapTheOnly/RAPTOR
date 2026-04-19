import React, { useMemo } from 'react';
import { Box, Chip, Divider, LinearProgress, Paper, Stack, Typography, alpha } from '@mui/material';
import {
  Assessment as AssessmentIcon,
  Description as DescriptionIcon,
  Insights as InsightsIcon,
  InsertPageBreak as InsertPageBreakIcon,
  TableView as TableViewIcon
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getBlockLabel } from '../../report-template-utils';

const PLACEHOLDER_PATTERN = /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g;

const SAMPLE_CONTEXT = {
  generated_at: '2026-02-10 12:45 UTC',
  record: {
    name: 'payments.example.com',
    ip_address: '10.20.10.15',
    source: 'Cloud',
    application_name: 'Payments Platform'
  },
  pentest: {
    status: 'In Progress',
    tested_by: 'senior.pentester',
    test_start_date: '2026-02-01',
    test_end_date: '2026-02-18',
    service_desk_link: 'https://servicedesk.example.com/TKT-1425',
    open_ports: '22, 443, 587',
    vulnerable: 'Yes',
    vulnerability_fixed: 'No'
  },
  metrics: {
    vulnerability_count: 9,
    critical_count: 1,
    high_count: 3,
    medium_count: 4,
    low_count: 1,
    critical_high_count: 4,
    open_findings: 9,
    fixed_findings: 0,
    open_ports_count: 3,
    checklist_total: 142,
    checklist_completed: 98,
    checklist_irrelevant: 14,
    checklist_unstarted: 30,
    checklist_percentage: 69
  }
};

const flattenObject = (value, prefix = '', output = {}) => {
  if (Array.isArray(value)) {
    value.forEach((entry, index) => flattenObject(entry, prefix ? `${prefix}.${index}` : `${index}`, output));
    return output;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, entry]) => {
      flattenObject(entry, prefix ? `${prefix}.${key}` : key, output);
    });
    return output;
  }
  output[prefix] = value == null ? '' : String(value);
  return output;
};

const buildPreviewBars = (rows, theme) => (
  <Stack spacing={0.75}>
    {rows.map((row) => (
      <Box key={row.label}>
        <Box display="flex" justifyContent="space-between" mb={0.25}>
          <Typography variant="caption">{row.label}</Typography>
          <Typography variant="caption" color="text.secondary">
            {row.value}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={row.value}
          sx={{
            height: 6,
            borderRadius: 4,
            backgroundColor: alpha(theme.palette.primary.main, 0.12)
          }}
        />
      </Box>
    ))}
  </Stack>
);

const ReportTemplateLivePreview = ({ templateForm }) => {
  const theme = useTheme();

  const resolver = useMemo(() => {
    const placeholders = templateForm?.placeholders || {};
    const context = {
      ...SAMPLE_CONTEXT,
      placeholders
    };
    const flat = flattenObject(context);
    Object.keys(placeholders).forEach((key) => {
      flat[key] = placeholders[key];
      flat[`placeholders.${key}`] = placeholders[key];
    });
    return (rawValue) => {
      const text = String(rawValue || '');
      return text.replace(PLACEHOLDER_PATTERN, (_, key) => flat[key] || '');
    };
  }, [templateForm?.placeholders]);

  const blocks = Array.isArray(templateForm?.blocks) ? templateForm.blocks : [];

  const renderBlockPreview = (block, index) => {
    const title = resolver(block.title || getBlockLabel(block.type));
    const commonHeader = (
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          {title || getBlockLabel(block.type)}
        </Typography>
        <Chip size="small" label={getBlockLabel(block.type)} />
      </Box>
    );

    switch (block.type) {
      case 'cover':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Typography variant="body2" sx={{ mb: 0.75 }}>
              {resolver(block.subtitle || '{{report_subtitle}}')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Prepared for {resolver('{{record.name}}')} by {resolver('{{pentest.tested_by}}')}
            </Typography>
          </Paper>
        );
      case 'engagement_overview':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Stack spacing={0.5}>
              <Typography variant="caption">Target: {resolver('{{record.name}}')}</Typography>
              <Typography variant="caption">IP: {resolver('{{record.ip_address}}')}</Typography>
              <Typography variant="caption">Status: {resolver('{{pentest.status}}')}</Typography>
              <Typography variant="caption">Tester: {resolver('{{pentest.tested_by}}')}</Typography>
            </Stack>
          </Paper>
        );
      case 'key_metrics':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            {buildPreviewBars(
              [
                { label: 'Checklist Completion', value: Number(SAMPLE_CONTEXT.metrics.checklist_percentage) },
                {
                  label: 'Critical / High',
                  value: Math.min(Number(SAMPLE_CONTEXT.metrics.critical_high_count) * 10, 100)
                },
                { label: 'Open Findings', value: Math.min(Number(SAMPLE_CONTEXT.metrics.open_findings) * 8, 100) }
              ],
              theme
            )}
          </Paper>
        );
      case 'chart':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Box display="flex" alignItems="center" gap={1}>
              <AssessmentIcon fontSize="small" color="primary" />
              <Typography variant="caption" color="text.secondary">
                Chart source: {block.chart || 'vulnerability_severity'}
              </Typography>
            </Box>
          </Paper>
        );
      case 'open_ports':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Box display="flex" alignItems="center" gap={1}>
              <TableViewIcon fontSize="small" color="primary" />
              <Typography variant="caption">22, 443, 587 (SSH/HTTPS/SMTP Submission)</Typography>
            </Box>
          </Paper>
        );
      case 'markdown':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Box display="flex" alignItems="center" gap={1}>
              <DescriptionIcon fontSize="small" color="primary" />
              <Typography variant="caption" color="text.secondary">
                Markdown field: {block.field || 'description'}
              </Typography>
            </Box>
          </Paper>
        );
      case 'checklists':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Typography variant="caption">
              Completion: {resolver('{{metrics.checklist_completed}}')}/
              {resolver('{{metrics.checklist_total}}')} (
              {resolver('{{metrics.checklist_percentage}}')}%)
            </Typography>
          </Paper>
        );
      case 'vulnerabilities':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Box display="flex" alignItems="center" gap={1}>
              <InsightsIcon fontSize="small" color="primary" />
              <Typography variant="caption">
                Findings: {resolver('{{metrics.vulnerability_count}}')} total,{' '}
                {resolver('{{metrics.critical_high_count}}')} critical/high
              </Typography>
            </Box>
          </Paper>
        );
      case 'text':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Typography variant="caption" color="text.secondary">
              {resolver(block.content || 'Summary text block.')}
            </Typography>
          </Paper>
        );
      case 'page_break':
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Box display="flex" alignItems="center" gap={1}>
              <InsertPageBreakIcon fontSize="small" color="primary" />
              <Typography variant="caption" color="text.secondary">
                New PDF page starts here.
              </Typography>
            </Box>
            <Divider sx={{ mt: 1, borderStyle: 'dashed' }} />
          </Paper>
        );
      default:
        return (
          <Paper key={block._uiId || index} variant="outlined" sx={{ p: 1.5 }}>
            {commonHeader}
            <Typography variant="caption" color="text.secondary">
              Custom block preview
            </Typography>
          </Paper>
        );
    }
  };

  return (
    <Stack spacing={1.25}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        Live Preview
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Preview uses sample data and updates immediately as you edit blocks and placeholders.
      </Typography>
      {blocks.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <Typography variant="caption" color="text.secondary">
            No blocks added yet.
          </Typography>
        </Paper>
      ) : (
        blocks.map((block, index) => renderBlockPreview(block, index))
      )}
    </Stack>
  );
};

export default ReportTemplateLivePreview;
