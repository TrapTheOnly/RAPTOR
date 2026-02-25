import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  alpha
} from '@mui/material';
import {
  Add as AddIcon,
  Article as ArticleIcon,
  Check as CheckIcon,
  CloudUpload as CloudUploadIcon,
  ContentCopy as ContentCopyIcon,
  Delete as DeleteIcon,
  DragIndicator as DragIndicatorIcon,
  Palette as PaletteIcon,
  RestartAlt as RestartAltIcon,
  Settings as SettingsIcon,
  ViewStream as ViewStreamIcon
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import SectionHeader from './SectionHeader';
import {
  createBlockByType,
  getBlockLabel,
  REPORT_CHART_OPTIONS,
  REPORT_MARKDOWN_FIELD_OPTIONS,
  REPORT_TEMPLATE_VARIABLE_GROUPS
} from '../report-template-utils';

const CONTROL_HEIGHT = 56;
const BLOCK_TYPE_MIME = 'application/x-raptor-report-block-type';
const BLOCK_ID_MIME = 'application/x-raptor-report-block-id';
const BLOCK_LIBRARY_KEY_MIME = 'application/x-raptor-report-library-item-key';
const BLOCK_DND_MIME = 'application/x-raptor-report-block-payload';

const DEFAULT_MANAGEMENT_SUMMARY =
  'Findings detected: {{metrics.vulnerability_count}}. Critical/High findings: {{metrics.critical_high_count}}.';

const REPORT_FLOW_LIBRARY_ITEMS = [
  {
    key: 'cover_page',
    type: 'cover',
    label: 'Cover Page',
    description: 'Main title section with subtitle and optional logo.',
    maxUses: 1,
    preset: {
      title: '{{report_title}}',
      subtitle: '{{report_subtitle}}',
      show_logo: true
    },
    match: (block) => block.type === 'cover'
  },
  {
    key: 'engagement_overview',
    type: 'engagement_overview',
    label: 'Engagement Overview',
    description: 'Target, tester, testing window, and high-level status.',
    maxUses: 1,
    preset: {
      title: 'Engagement Overview'
    },
    match: (block) => block.type === 'engagement_overview'
  },
  {
    key: 'risk_snapshot',
    type: 'key_metrics',
    label: 'Risk Snapshot',
    description: 'Executive KPI summary for risk and progress.',
    maxUses: 1,
    preset: {
      title: 'Risk Snapshot'
    },
    match: (block) => block.type === 'key_metrics'
  },
  {
    key: 'chart_vulnerability_severity',
    type: 'chart',
    label: 'Vulnerability Severity Distribution',
    description: 'Chart of critical/high/medium/low findings.',
    maxUses: 1,
    preset: {
      title: 'Vulnerability Severity Distribution',
      chart: 'vulnerability_severity'
    },
    match: (block) => block.type === 'chart' && block.chart === 'vulnerability_severity'
  },
  {
    key: 'chart_checklist_completion',
    type: 'chart',
    label: 'Checklist Completion Status',
    description: 'Completed, unstarted, and irrelevant checklist split.',
    maxUses: 1,
    preset: {
      title: 'Checklist Completion Status',
      chart: 'checklist_completion'
    },
    match: (block) => block.type === 'chart' && block.chart === 'checklist_completion'
  },
  {
    key: 'chart_remediation_status',
    type: 'chart',
    label: 'Open vs Remediated Findings',
    description: 'Open findings versus fixed findings breakdown.',
    maxUses: 1,
    preset: {
      title: 'Open vs Remediated Findings',
      chart: 'vulnerability_fix_status'
    },
    match: (block) => block.type === 'chart' && block.chart === 'vulnerability_fix_status'
  },
  {
    key: 'open_ports',
    type: 'open_ports',
    label: 'Open Ports',
    description: 'Rendered table of open ports and mapped services.',
    maxUses: 1,
    preset: {
      title: 'Open Ports'
    },
    match: (block) => block.type === 'open_ports'
  },
  {
    key: 'asset_description',
    type: 'markdown',
    label: 'Asset Description',
    description: 'Markdown content from asset description field.',
    maxUses: 1,
    preset: {
      title: 'Asset Description',
      field: 'description'
    },
    match: (block) => block.type === 'markdown' && block.field === 'description'
  },
  {
    key: 'security_details',
    type: 'markdown',
    label: 'Security Details',
    description: 'Markdown content from security details/notes field.',
    maxUses: 1,
    preset: {
      title: 'Security Details',
      field: 'notes'
    },
    match: (block) => block.type === 'markdown' && block.field === 'notes'
  },
  {
    key: 'checklist_coverage',
    type: 'checklists',
    label: 'Checklist Coverage',
    description: 'Checklist progress and completion ratio by template.',
    maxUses: 1,
    preset: {
      title: 'Checklist Coverage'
    },
    match: (block) => block.type === 'checklists'
  },
  {
    key: 'detailed_findings',
    type: 'vulnerabilities',
    label: 'Detailed Findings',
    description: 'Vulnerability details including CVSS and descriptions.',
    maxUses: 1,
    preset: {
      title: 'Detailed Findings',
      include_descriptions: true
    },
    match: (block) => block.type === 'vulnerabilities'
  },
  {
    key: 'management_summary',
    type: 'text',
    label: 'Management Summary',
    description: 'Executive narrative with variable placeholders.',
    maxUses: 1,
    preset: {
      title: 'Management Summary',
      content: DEFAULT_MANAGEMENT_SUMMARY
    },
    match: (block) =>
      block.type === 'text' &&
      String(block.title || '').trim().toLowerCase() === 'management summary'
  },
  {
    key: 'custom_chart',
    type: 'chart',
    label: 'Custom Chart (Reusable)',
    description: 'Reusable chart block. Choose any chart type in settings.',
    maxUses: null,
    preset: {
      title: 'Custom Chart',
      chart: 'vulnerability_severity'
    },
    match: (block) => block._libraryItemKey === 'custom_chart'
  },
  {
    key: 'custom_markdown',
    type: 'markdown',
    label: 'Custom Markdown (Reusable)',
    description: 'Reusable markdown block. Choose any markdown source.',
    maxUses: null,
    preset: {
      title: 'Custom Markdown',
      field: 'description'
    },
    match: (block) => block._libraryItemKey === 'custom_markdown'
  },
  {
    key: 'custom_text',
    type: 'text',
    label: 'Custom Text (Reusable)',
    description: 'Reusable free-text narrative block.',
    maxUses: null,
    preset: {
      title: 'Custom Summary',
      content: 'Add your custom executive summary here.'
    },
    match: (block) => block._libraryItemKey === 'custom_text'
  },
  {
    key: 'page_break',
    type: 'page_break',
    label: 'Page Break (Reusable)',
    description: 'Starts a new PDF page before the next section.',
    maxUses: null,
    preset: {
      title: 'Page Break'
    },
    match: (block) => block.type === 'page_break'
  }
];

const getBlockId = (block, index) => block?._uiId || `block-${index}`;

const parsePayload = (rawValue) => {
  if (!rawValue) return null;
  try {
    const parsed = JSON.parse(rawValue);
    if (
      parsed &&
      typeof parsed === 'object' &&
      (parsed.kind === 'library' || parsed.kind === 'flow')
    ) {
      return parsed;
    }
  } catch (_error) {
    return null;
  }
  return null;
};

const clampIndex = (value, size) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed)) return 0;
  if (parsed < 0) return 0;
  if (parsed > size) return size;
  return parsed;
};

const getBlockSummary = (block) => {
  if (!block) return '';

  switch (block.type) {
    case 'cover':
      return block.subtitle || 'Cover section for title, subtitle, and logo.';
    case 'engagement_overview':
      return 'Target, tester, dates, and engagement scope.';
    case 'key_metrics':
      return 'Executive metrics and risk indicators.';
    case 'chart':
      return (
        REPORT_CHART_OPTIONS.find((option) => option.value === block.chart)?.label ||
        'Chart block'
      );
    case 'open_ports':
      return 'Open ports table and service hints.';
    case 'markdown':
      return (
        REPORT_MARKDOWN_FIELD_OPTIONS.find((option) => option.value === block.field)
          ?.label || 'Markdown field'
      );
    case 'checklists':
      return 'Checklist completion and coverage details.';
    case 'vulnerabilities':
      return block.include_descriptions
        ? 'Detailed findings with descriptions.'
        : 'Findings summary table.';
    case 'text':
      return block.content || 'Free-form management summary.';
    case 'page_break':
      return 'Hard break before the next section.';
    default:
      return getBlockLabel(block.type);
  }
};

const headerFieldSx = {
  '& .MuiOutlinedInput-root': {
    height: CONTROL_HEIGHT
  },
  '& .MuiInputBase-input': {
    fontSize: '0.9rem'
  },
  '& .MuiInputLabel-root': {
    fontSize: '0.84rem'
  }
};

const ReportTemplatesSection = ({
  loading,
  selectedTemplate,
  templateForm,
  onChangeTemplateForm,
  onUploadLogo,
  onSaveTemplate,
  onDeleteTemplate,
  onResetTemplate
}) => {
  const theme = useTheme();
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [dragOverSlot, setDragOverSlot] = useState('');
  const [activeTab, setActiveTab] = useState('builder');
  const [copiedVariable, setCopiedVariable] = useState('');

  const blocks = useMemo(
    () => (Array.isArray(templateForm?.blocks) ? templateForm.blocks : []),
    [templateForm?.blocks]
  );

  const libraryByKey = useMemo(
    () => new Map(REPORT_FLOW_LIBRARY_ITEMS.map((item) => [item.key, item])),
    []
  );

  const selectedBlockIndex = useMemo(
    () => blocks.findIndex((block) => block?._uiId === selectedBlockId),
    [blocks, selectedBlockId]
  );

  const selectedBlock = selectedBlockIndex >= 0 ? blocks[selectedBlockIndex] : null;

  useEffect(() => {
    if (!blocks.length) {
      setSelectedBlockId(null);
      return;
    }

    const selectedExists = blocks.some((block, index) => {
      const blockId = getBlockId(block, index);
      return blockId === selectedBlockId;
    });

    if (!selectedExists) {
      setSelectedBlockId(getBlockId(blocks[0], 0));
    }
  }, [blocks, selectedBlockId]);

  const libraryUsage = useMemo(() => {
    const usage = {};
    REPORT_FLOW_LIBRARY_ITEMS.forEach((item) => {
      usage[item.key] = blocks.reduce((count, block) => {
        const blockLibraryKey = block?._libraryItemKey;
        if (blockLibraryKey) {
          return blockLibraryKey === item.key ? count + 1 : count;
        }
        if (item.match && item.match(block)) {
          return count + 1;
        }
        return count;
      }, 0);
    });
    return usage;
  }, [blocks]);

  const isItemAtLimit = (item) =>
    Number.isInteger(item.maxUses) && (libraryUsage[item.key] || 0) >= item.maxUses;

  const updateBlocks = (nextBlocks) => {
    onChangeTemplateForm('blocks', nextBlocks);
  };

  const updateBranding = (field, value) => {
    onChangeTemplateForm('branding', {
      ...(templateForm?.branding || {}),
      [field]: value
    });
  };

  const updatePlaceholders = (field, value) => {
    onChangeTemplateForm('placeholders', {
      ...(templateForm?.placeholders || {}),
      [field]: value
    });
  };

  const handleLogoUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !onUploadLogo) return;
    await onUploadLogo(file);
  };

  const updateSelectedBlock = (updater) => {
    if (selectedBlockIndex < 0) return;

    const nextBlocks = blocks.map((block, index) =>
      index === selectedBlockIndex ? updater(block) : block
    );
    updateBlocks(nextBlocks);
  };

  const updateSelectedBlockField = (field, value) => {
    updateSelectedBlock((block) => ({
      ...block,
      [field]: value
    }));
  };

  const createBlockFromLibraryItem = (item, index) => {
    const base = createBlockByType(item.type, index);
    return {
      ...base,
      ...item.preset,
      _libraryItemKey: item.key
    };
  };

  const findLibraryItemForLegacyType = (type) => {
    const byType = REPORT_FLOW_LIBRARY_ITEMS.filter((item) => item.type === type);
    if (!byType.length) return null;
    return byType.find((item) => !isItemAtLimit(item)) || byType[0];
  };

  const addLibraryItemAt = (itemKey, index) => {
    const item = libraryByKey.get(itemKey);
    if (!item || isItemAtLimit(item)) return false;

    const insertIndex = clampIndex(index, blocks.length);
    const newBlock = createBlockFromLibraryItem(item, insertIndex);
    const nextBlocks = [...blocks];
    nextBlocks.splice(insertIndex, 0, newBlock);
    updateBlocks(nextBlocks);
    setSelectedBlockId(newBlock._uiId || getBlockId(newBlock, insertIndex));
    return true;
  };

  const moveBlockById = (blockId, targetIndex) => {
    const fromIndex = blocks.findIndex((block, index) => getBlockId(block, index) === blockId);
    if (fromIndex < 0) return;

    let toIndex = clampIndex(targetIndex, blocks.length);
    if (fromIndex === toIndex || fromIndex + 1 === toIndex) return;

    const reordered = [...blocks];
    const [moved] = reordered.splice(fromIndex, 1);

    if (fromIndex < toIndex) {
      toIndex -= 1;
    }

    toIndex = clampIndex(toIndex, reordered.length);
    reordered.splice(toIndex, 0, moved);
    updateBlocks(reordered);
  };

  const removeSelectedBlock = () => {
    if (!selectedBlock) return;

    const nextBlocks = blocks.filter((_, index) => index !== selectedBlockIndex);
    updateBlocks(nextBlocks);

    if (!nextBlocks.length) {
      setSelectedBlockId(null);
      return;
    }

    const fallbackIndex = Math.max(0, selectedBlockIndex - 1);
    setSelectedBlockId(getBlockId(nextBlocks[fallbackIndex], fallbackIndex));
  };

  const handleLibraryDragStart = (event, item) => {
    if (isItemAtLimit(item)) {
      event.preventDefault();
      return;
    }

    const payload = JSON.stringify({ kind: 'library', itemKey: item.key });
    event.dataTransfer.effectAllowed = 'copyMove';
    event.dataTransfer.setData(BLOCK_DND_MIME, payload);
    event.dataTransfer.setData('text/plain', payload);
    event.dataTransfer.setData(BLOCK_LIBRARY_KEY_MIME, item.key);
    event.dataTransfer.setData(BLOCK_TYPE_MIME, item.type);
  };

  const handleFlowDragStart = (event, blockId) => {
    const payload = JSON.stringify({ kind: 'flow', blockId });
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData(BLOCK_DND_MIME, payload);
    event.dataTransfer.setData('text/plain', payload);
    event.dataTransfer.setData(BLOCK_ID_MIME, blockId);
    setDragOverSlot('');
  };

  const readDropPayload = (event) => {
    const rawPayload =
      event.dataTransfer.getData(BLOCK_DND_MIME) ||
      event.dataTransfer.getData('text/plain') ||
      '';
    const parsedPayload = parsePayload(rawPayload);
    if (parsedPayload) return parsedPayload;

    const itemKey = event.dataTransfer.getData(BLOCK_LIBRARY_KEY_MIME);
    if (itemKey) {
      return { kind: 'library', itemKey };
    }

    const legacyType = event.dataTransfer.getData(BLOCK_TYPE_MIME);
    if (legacyType) {
      return { kind: 'legacy-library-type', type: legacyType };
    }

    const legacyBlockId = event.dataTransfer.getData(BLOCK_ID_MIME);
    if (legacyBlockId) {
      return { kind: 'flow', blockId: legacyBlockId };
    }

    return null;
  };

  const handleDropAt = (event, targetIndex) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOverSlot('');

    const payload = readDropPayload(event);
    if (!payload) return;

    if (payload.kind === 'library') {
      addLibraryItemAt(payload.itemKey, targetIndex);
      return;
    }

    if (payload.kind === 'legacy-library-type') {
      const item = findLibraryItemForLegacyType(payload.type);
      if (item) {
        addLibraryItemAt(item.key, targetIndex);
      }
      return;
    }

    if (payload.kind === 'flow') {
      moveBlockById(payload.blockId, targetIndex);
      setSelectedBlockId(payload.blockId);
    }
  };

  const handleDragOverSlot = (event, slotKey) => {
    event.preventDefault();
    event.stopPropagation();
    const payload = readDropPayload(event);
    event.dataTransfer.dropEffect = payload?.kind === 'flow' ? 'move' : 'copy';
    setDragOverSlot(slotKey);
  };

  const handleFlowDragEnd = () => {
    setDragOverSlot('');
  };

  const moveSelectedBlock = (direction) => {
    if (selectedBlockIndex < 0) return;
    const nextIndex = selectedBlockIndex + direction;
    if (nextIndex < 0 || nextIndex >= blocks.length) return;

    const reordered = [...blocks];
    const [moved] = reordered.splice(selectedBlockIndex, 1);
    reordered.splice(nextIndex, 0, moved);
    updateBlocks(reordered);
  };

  const copyVariableToken = async (token) => {
    try {
      await navigator.clipboard.writeText(token);
      setCopiedVariable(token);
      setTimeout(() => {
        setCopiedVariable((current) => (current === token ? '' : current));
      }, 1500);
    } catch (_error) {
      setCopiedVariable(token);
    }
  };

  const renderBlockSettings = () => {
    if (!selectedBlock) {
      return (
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <Typography variant="caption" color="text.secondary">
            Select a block from report flow to configure it.
          </Typography>
        </Paper>
      );
    }

    const sourceItem =
      selectedBlock._libraryItemKey && libraryByKey.get(selectedBlock._libraryItemKey);

    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                Element Settings
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.72rem' }}>
                {sourceItem?.label || getBlockLabel(selectedBlock.type)}
              </Typography>
            </Box>
            <Stack direction="row" spacing={0.3}>
              <Tooltip title="Move up">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => moveSelectedBlock(-1)}
                    disabled={selectedBlockIndex <= 0}
                  >
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      ▲
                    </Typography>
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Move down">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => moveSelectedBlock(1)}
                    disabled={selectedBlockIndex < 0 || selectedBlockIndex >= blocks.length - 1}
                  >
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      ▼
                    </Typography>
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Remove element">
                <span>
                  <IconButton size="small" color="error" onClick={removeSelectedBlock}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            </Stack>
          </Box>

          <Stack spacing={0.9}>
            {selectedBlock.type !== 'page_break' && (
              <TextField
                size="small"
                label="Title"
                value={selectedBlock.title || ''}
                onChange={(event) => updateSelectedBlockField('title', event.target.value)}
                InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                inputProps={{ style: { fontSize: '0.84rem' } }}
              />
            )}

            {selectedBlock.type === 'cover' && (
              <>
                <TextField
                  size="small"
                  label="Subtitle"
                  value={selectedBlock.subtitle || ''}
                  onChange={(event) => updateSelectedBlockField('subtitle', event.target.value)}
                  InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                  inputProps={{ style: { fontSize: '0.84rem' } }}
                />
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={Boolean(selectedBlock.show_logo)}
                      onChange={(event) =>
                        updateSelectedBlockField('show_logo', event.target.checked)
                      }
                    />
                  }
                  label={<Typography sx={{ fontSize: '0.78rem' }}>Show logo</Typography>}
                  sx={{ m: 0 }}
                />
              </>
            )}

            {selectedBlock.type === 'chart' && (
              <TextField
                select
                size="small"
                label="Chart Type"
                value={selectedBlock.chart || 'vulnerability_severity'}
                onChange={(event) => updateSelectedBlockField('chart', event.target.value)}
                InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                inputProps={{ style: { fontSize: '0.84rem' } }}
              >
                {REPORT_CHART_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value} sx={{ fontSize: '0.82rem' }}>
                    {option.label}
                  </MenuItem>
                ))}
              </TextField>
            )}

            {selectedBlock.type === 'markdown' && (
              <TextField
                select
                size="small"
                label="Markdown Field"
                value={selectedBlock.field || 'description'}
                onChange={(event) => updateSelectedBlockField('field', event.target.value)}
                InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                inputProps={{ style: { fontSize: '0.84rem' } }}
              >
                {REPORT_MARKDOWN_FIELD_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value} sx={{ fontSize: '0.82rem' }}>
                    {option.label}
                  </MenuItem>
                ))}
              </TextField>
            )}

            {selectedBlock.type === 'vulnerabilities' && (
              <FormControlLabel
                control={
                  <Switch
                    size="small"
                    checked={Boolean(selectedBlock.include_descriptions)}
                    onChange={(event) =>
                      updateSelectedBlockField('include_descriptions', event.target.checked)
                    }
                  />
                }
                label={
                  <Typography sx={{ fontSize: '0.78rem' }}>
                    Include detailed descriptions
                  </Typography>
                }
                sx={{ m: 0 }}
              />
            )}

            {selectedBlock.type === 'text' && (
              <TextField
                size="small"
                multiline
                minRows={4}
                label="Content"
                value={selectedBlock.content || ''}
                onChange={(event) => updateSelectedBlockField('content', event.target.value)}
                InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                inputProps={{ style: { fontSize: '0.84rem' } }}
              />
            )}

            {selectedBlock.type === 'page_break' && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.74rem' }}>
                This block inserts a page break in generated PDF.
              </Typography>
            )}
          </Stack>
        </CardContent>
      </Card>
    );
  };

  const renderVariablesTab = () => (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.75 }}>
          Template Variables
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Click any token to copy it, then paste it into titles, text summaries, or custom markdown blocks.
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gap: 1.2,
            gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' }
          }}
        >
          {REPORT_TEMPLATE_VARIABLE_GROUPS.map((group) => (
            <Card key={group.key} variant="outlined">
              <CardContent sx={{ p: 1.2, '&:last-child': { pb: 1.2 } }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.84rem', mb: 0.8 }}>
                  {group.label}
                </Typography>

                <Box display="flex" flexWrap="wrap" gap={0.6}>
                  {group.variables.map((variable) => {
                    const copied = copiedVariable === variable.token;
                    return (
                      <Button
                        key={variable.token}
                        variant={copied ? 'contained' : 'outlined'}
                        size="small"
                        startIcon={<ContentCopyIcon sx={{ fontSize: 14 }} />}
                        onClick={() => copyVariableToken(variable.token)}
                        sx={{
                          textTransform: 'none',
                          alignItems: 'flex-start',
                          px: 0.85,
                          py: 0.55,
                          borderRadius: 1,
                          minWidth: 0
                        }}
                      >
                        <Box textAlign="left" lineHeight={1.05}>
                          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>
                            {variable.label}
                          </Typography>
                          <Typography
                            component="span"
                            sx={{
                              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                              fontSize: '0.67rem'
                            }}
                          >
                            {variable.token}
                          </Typography>
                        </Box>
                      </Button>
                    );
                  })}
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Card>
      <CardContent>
        <SectionHeader icon={ArticleIcon} title="Report Templates" />

        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.25}>
          <Typography variant="body2" color="text.secondary">
            Templates are selected from left navigation. Use builder for layout and variables tab for placeholders.
          </Typography>
          <Tabs
            value={activeTab}
            onChange={(_, value) => setActiveTab(value)}
            sx={{ minHeight: 34 }}
          >
            <Tab value="builder" label="Builder" sx={{ minHeight: 34, fontSize: '0.76rem' }} />
            <Tab value="variables" label="Variables" sx={{ minHeight: 34, fontSize: '0.76rem' }} />
          </Tabs>
        </Box>

        {activeTab === 'variables' ? (
          renderVariablesTab()
        ) : (
          <>
            <Box
              sx={{
                display: 'grid',
                gap: 1,
                gridTemplateColumns: {
                  xs: '1fr',
                  md: 'repeat(2, minmax(0, 1fr))',
                  xl: 'repeat(4, minmax(0, 1fr))'
                },
                mb: 0.75
              }}
            >
              <TextField
                label="Template Key"
                size="small"
                value={templateForm.key}
                onChange={(event) => onChangeTemplateForm('key', event.target.value)}
                disabled={Boolean(selectedTemplate?.is_system)}
                sx={headerFieldSx}
              />
              <TextField
                label="Display Name"
                size="small"
                value={templateForm.name}
                onChange={(event) => onChangeTemplateForm('name', event.target.value)}
                sx={headerFieldSx}
              />
              <TextField
                label="Description"
                size="small"
                value={templateForm.description}
                onChange={(event) => onChangeTemplateForm('description', event.target.value)}
                sx={headerFieldSx}
              />
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: 1,
                  px: 1.25,
                  height: CONTROL_HEIGHT,
                  boxSizing: 'border-box'
                }}
              >
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(templateForm.enabled)}
                      onChange={(event) => onChangeTemplateForm('enabled', event.target.checked)}
                    />
                  }
                  label="Template enabled"
                  sx={{
                    m: 0,
                    '& .MuiFormControlLabel-label': {
                      fontSize: '0.9rem',
                      fontWeight: 500
                    }
                  }}
                />
                {selectedTemplate?.is_system && (
                  <Chip
                    size="small"
                    color={selectedTemplate.is_customized ? 'warning' : 'info'}
                    label={selectedTemplate.is_customized ? 'Customized' : 'System'}
                  />
                )}
              </Box>
            </Box>

            {selectedTemplate?.is_system && (
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1.25, display: 'block' }}>
                System template key is locked.
              </Typography>
            )}

            <Box
              sx={{
                display: 'grid',
                gap: 1.25,
                gridTemplateColumns: {
                  xs: '1fr',
                  xl: 'minmax(235px, 280px) minmax(0, 1fr) minmax(280px, 330px)'
                }
              }}
            >
              <Card variant="outlined" sx={{ height: 'fit-content' }}>
                <CardContent sx={{ p: 1.2, '&:last-child': { pb: 1.2 } }}>
                  <Box display="flex" alignItems="center" gap={0.75} mb={0.75}>
                    <PaletteIcon color="primary" sx={{ fontSize: 18 }} />
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.88rem' }}>
                      Element Library
                    </Typography>
                  </Box>

                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.72rem' }}>
                    Names match default report flow. Some are single-use; reusable items are marked.
                  </Typography>

                  <Stack spacing={0.72} sx={{ mt: 1 }}>
                    {REPORT_FLOW_LIBRARY_ITEMS.map((item) => {
                      const usage = libraryUsage[item.key] || 0;
                      const atLimit = isItemAtLimit(item);
                      const isReusable = !Number.isInteger(item.maxUses);

                      return (
                        <Paper
                          key={item.key}
                          variant="outlined"
                          draggable={!atLimit}
                          onDragStart={(event) => handleLibraryDragStart(event, item)}
                          sx={{
                            px: 0.85,
                            py: 0.7,
                            borderColor: atLimit
                              ? alpha(theme.palette.success.main, 0.45)
                              : theme.palette.divider,
                            backgroundColor: atLimit
                              ? alpha(theme.palette.success.main, 0.08)
                              : theme.palette.background.paper,
                            opacity: atLimit ? 0.8 : 1,
                            cursor: atLimit ? 'not-allowed' : 'grab'
                          }}
                        >
                          <Box display="flex" alignItems="center" justifyContent="space-between" gap={0.7}>
                            <Box sx={{ minWidth: 0 }}>
                              <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, lineHeight: 1.2 }}>
                                {item.label}
                              </Typography>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ fontSize: '0.68rem', lineHeight: 1.2 }}
                              >
                                {item.description}
                              </Typography>
                            </Box>

                            <Stack direction="row" spacing={0.4} alignItems="center">
                              <Chip
                                size="small"
                                color={atLimit ? 'success' : 'default'}
                                label={
                                  isReusable
                                    ? `${usage} used · reusable`
                                    : `${usage}/${item.maxUses}`
                                }
                                sx={{ height: 18, fontSize: '0.63rem' }}
                              />
                              {!atLimit && (
                                <Tooltip title="Add element">
                                  <IconButton
                                    size="small"
                                    onClick={() => addLibraryItemAt(item.key, blocks.length)}
                                    disabled={loading}
                                  >
                                    <AddIcon sx={{ fontSize: 15 }} />
                                  </IconButton>
                                </Tooltip>
                              )}
                              <DragIndicatorIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                            </Stack>
                          </Box>
                        </Paper>
                      );
                    })}
                  </Stack>
                </CardContent>
              </Card>

              <Card variant="outlined">
                <CardContent sx={{ p: 1.2, '&:last-child': { pb: 1.2 } }}>
                  <Box display="flex" alignItems="center" gap={0.75} mb={1}>
                    <ViewStreamIcon color="primary" sx={{ fontSize: 18 }} />
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.88rem' }}>
                      Report Page Flow
                    </Typography>
                  </Box>

                  {blocks.length === 0 ? (
                    <Paper
                      variant="outlined"
                      onDragOver={(event) => handleDragOverSlot(event, 'empty')}
                      onDrop={(event) => handleDropAt(event, 0)}
                      sx={{
                        minHeight: 300,
                        p: 2,
                        display: 'grid',
                        placeItems: 'center',
                        borderStyle: 'dashed',
                        borderColor:
                          dragOverSlot === 'empty'
                            ? theme.palette.primary.main
                            : theme.palette.divider,
                        backgroundColor:
                          dragOverSlot === 'empty'
                            ? alpha(theme.palette.primary.main, 0.08)
                            : theme.palette.background.paper
                      }}
                    >
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>
                        Drop elements here to compose the report.
                      </Typography>
                    </Paper>
                  ) : (
                    <Stack
                      spacing={0.8}
                      onDragOver={(event) => handleDragOverSlot(event, 'flow-container')}
                      onDrop={(event) => handleDropAt(event, blocks.length)}
                    >
                      {blocks.map((block, index) => {
                        const blockId = getBlockId(block, index);
                        const selected = blockId === selectedBlockId;
                        const slotKey = `before-${blockId}`;
                        const surfaceSlotKey = `surface-${blockId}`;
                        const sourceItem =
                          block._libraryItemKey && libraryByKey.get(block._libraryItemKey);

                        return (
                          <Box key={blockId}>
                            <Box
                              onDragOver={(event) => handleDragOverSlot(event, slotKey)}
                              onDrop={(event) => handleDropAt(event, index)}
                              sx={{
                                height: 14,
                                borderRadius: 4,
                                mb: 0.5,
                                backgroundColor:
                                  dragOverSlot === slotKey
                                    ? alpha(theme.palette.primary.main, 0.38)
                                    : 'transparent'
                              }}
                            />

                            <Paper
                              variant="outlined"
                              draggable
                              onDragStart={(event) => handleFlowDragStart(event, blockId)}
                              onDragEnd={handleFlowDragEnd}
                              onMouseDown={() => setSelectedBlockId(blockId)}
                              onDragOver={(event) => handleDragOverSlot(event, surfaceSlotKey)}
                              onDrop={(event) => handleDropAt(event, index + 1)}
                              sx={{
                                p: 0.95,
                                borderColor: selected
                                  ? theme.palette.primary.main
                                  : theme.palette.divider,
                                borderWidth: selected ? 2 : 1,
                                borderStyle: 'solid',
                                backgroundColor: selected
                                  ? alpha(theme.palette.primary.main, 0.08)
                                  : theme.palette.background.paper,
                                cursor: 'grab',
                                outline:
                                  dragOverSlot === surfaceSlotKey
                                    ? `2px dashed ${theme.palette.primary.main}`
                                    : 'none'
                              }}
                            >
                              <Box
                                display="flex"
                                alignItems="center"
                                justifyContent="space-between"
                                mb={0.45}
                              >
                                <Box
                                  display="flex"
                                  alignItems="center"
                                  gap={0.5}
                                  sx={{ minWidth: 0 }}
                                >
                                  <DragIndicatorIcon
                                    sx={{ fontSize: 14, color: 'text.secondary' }}
                                  />
                                  <Typography
                                    sx={{
                                      fontSize: '0.79rem',
                                      fontWeight: 700,
                                      lineHeight: 1.2,
                                      whiteSpace: 'nowrap',
                                      textOverflow: 'ellipsis',
                                      overflow: 'hidden'
                                    }}
                                  >
                                    {block.title || sourceItem?.label || getBlockLabel(block.type)}
                                  </Typography>
                                </Box>
                                <Chip
                                  size="small"
                                  label={sourceItem?.label || getBlockLabel(block.type)}
                                  sx={{ height: 18, fontSize: '0.61rem' }}
                                />
                              </Box>

                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden',
                                  fontSize: '0.69rem'
                                }}
                              >
                                {getBlockSummary(block)}
                              </Typography>
                            </Paper>
                          </Box>
                        );
                      })}

                      <Box
                        onDragOver={(event) => handleDragOverSlot(event, 'end')}
                        onDrop={(event) => handleDropAt(event, blocks.length)}
                        sx={{
                          height: 18,
                          borderRadius: 1,
                          border: `1px dashed ${
                            dragOverSlot === 'end'
                              ? theme.palette.primary.main
                              : theme.palette.divider
                          }`,
                          backgroundColor:
                            dragOverSlot === 'end'
                              ? alpha(theme.palette.primary.main, 0.08)
                              : 'transparent',
                          display: 'grid',
                          placeItems: 'center'
                        }}
                      >
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ fontSize: '0.68rem' }}
                        >
                          Drop here to place at end
                        </Typography>
                      </Box>
                    </Stack>
                  )}
                </CardContent>
              </Card>

              <Stack spacing={1.1}>
                {renderBlockSettings()}

                <Card variant="outlined">
                  <CardContent sx={{ p: 1.4, '&:last-child': { pb: 1.4 } }}>
                    <Box display="flex" alignItems="center" gap={0.65} mb={0.9}>
                      <SettingsIcon color="primary" sx={{ fontSize: 17 }} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.86rem' }}>
                        Branding
                      </Typography>
                    </Box>
                    <Stack spacing={0.9}>
                      <TextField
                        size="small"
                        label="Company"
                        value={templateForm.branding?.company_name || ''}
                        onChange={(event) => updateBranding('company_name', event.target.value)}
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                      <TextField
                        size="small"
                        label="Logo Asset"
                        value={
                          templateForm.branding?.logo_asset_id
                            ? `Logo uploaded`
                            : 'No logo uploaded'
                        }
                        InputProps={{ readOnly: true }}
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                      <Box display="flex" gap={0.8}>
                        <Button
                          size="small"
                          variant="outlined"
                          component="label"
                          startIcon={<CloudUploadIcon />}
                          disabled={loading || !selectedTemplate?.id}
                        >
                          Upload PNG Logo
                          <input
                            hidden
                            type="file"
                            accept="image/png"
                            onChange={handleLogoUpload}
                          />
                        </Button>
                        <Button
                          size="small"
                          variant="text"
                          color="warning"
                          disabled={loading || !templateForm.branding?.logo_asset_id}
                          onClick={() =>
                            onChangeTemplateForm('branding', {
                              ...(templateForm?.branding || {}),
                              logo_asset_id: null,
                              logo_url: ''
                            })
                          }
                        >
                          Remove Logo
                        </Button>
                      </Box>
                      <Box
                        sx={{
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr',
                          gap: 0.8
                        }}
                      >
                        <TextField
                          size="small"
                          type="color"
                          label="Primary"
                          InputLabelProps={{ shrink: true, sx: { fontSize: '0.78rem' } }}
                          value={templateForm.branding?.primary_color || '#0B5CAD'}
                          onChange={(event) =>
                            updateBranding('primary_color', event.target.value)
                          }
                        />
                        <TextField
                          size="small"
                          type="color"
                          label="Accent"
                          InputLabelProps={{ shrink: true, sx: { fontSize: '0.78rem' } }}
                          value={templateForm.branding?.accent_color || '#1E293B'}
                          onChange={(event) =>
                            updateBranding('accent_color', event.target.value)
                          }
                        />
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>

                <Card variant="outlined">
                  <CardContent sx={{ p: 1.4, '&:last-child': { pb: 1.4 } }}>
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 700, fontSize: '0.86rem', mb: 0.9 }}
                    >
                      Placeholders
                    </Typography>
                    <Stack spacing={0.85}>
                      <TextField
                        size="small"
                        label="Report Title"
                        value={templateForm.placeholders?.report_title || ''}
                        onChange={(event) =>
                          updatePlaceholders('report_title', event.target.value)
                        }
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                      <TextField
                        size="small"
                        label="Report Subtitle"
                        value={templateForm.placeholders?.report_subtitle || ''}
                        onChange={(event) =>
                          updatePlaceholders('report_subtitle', event.target.value)
                        }
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                      <TextField
                        size="small"
                        label="Prepared By"
                        value={templateForm.placeholders?.prepared_by || ''}
                        onChange={(event) =>
                          updatePlaceholders('prepared_by', event.target.value)
                        }
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                      <TextField
                        size="small"
                        label="Prepared For"
                        value={templateForm.placeholders?.prepared_for || ''}
                        onChange={(event) =>
                          updatePlaceholders('prepared_for', event.target.value)
                        }
                        InputLabelProps={{ sx: { fontSize: '0.78rem' } }}
                        inputProps={{ style: { fontSize: '0.84rem' } }}
                      />
                    </Stack>
                  </CardContent>
                </Card>
              </Stack>
            </Box>

            <Divider sx={{ my: 1.5 }} />

            <Box display="flex" justifyContent="space-between" alignItems="center" gap={1}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: '0.7rem' }}
              >
                Use the Variables tab to copy placeholders into summary/content fields.
              </Typography>
              <Stack direction="row" spacing={0.8}>
                {selectedTemplate?.is_system && (
                  <Button
                    variant="outlined"
                    color="warning"
                    size="small"
                    startIcon={<RestartAltIcon />}
                    onClick={() => onResetTemplate(selectedTemplate)}
                    disabled={loading || !selectedTemplate.is_customized}
                  >
                    Reset
                  </Button>
                )}
                {selectedTemplate && !selectedTemplate.is_system && (
                  <Button
                    variant="outlined"
                    color="error"
                    size="small"
                    startIcon={<DeleteIcon />}
                    onClick={() => onDeleteTemplate(selectedTemplate.id, selectedTemplate.name)}
                    disabled={loading}
                  >
                    Delete
                  </Button>
                )}
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<CheckIcon />}
                  onClick={onSaveTemplate}
                  disabled={loading}
                >
                  {selectedTemplate ? 'Save Changes' : 'Create Template'}
                </Button>
              </Stack>
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default ReportTemplatesSection;
