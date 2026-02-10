import React, { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControlLabel,
  IconButton,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  alpha
} from '@mui/material';
import {
  Add as AddIcon,
  Article as ArticleIcon,
  Check as CheckIcon,
  Delete as DeleteIcon,
  DragIndicator as DragIndicatorIcon,
  Edit as EditIcon,
  Palette as PaletteIcon,
  RestartAlt as RestartAltIcon,
  ViewCarousel as ViewCarouselIcon
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import SectionHeader from './SectionHeader';
import {
  createBlockByType,
  getBlockLabel,
  REPORT_BLOCK_LIBRARY,
  REPORT_CHART_OPTIONS,
  REPORT_MARKDOWN_FIELD_OPTIONS
} from '../report-template-utils';
import ReportTemplateLivePreview from './report-templates/ReportTemplateLivePreview';

const ReportTemplatesSection = ({
  loading,
  templates,
  selectedTemplateId,
  selectedTemplate,
  templateForm,
  onCreateNewTemplate,
  onSelectTemplate,
  onChangeTemplateForm,
  onSaveTemplate,
  onDeleteTemplate,
  onResetTemplate
}) => {
  const theme = useTheme();
  const [draggingIndex, setDraggingIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const blocks = useMemo(
    () => (Array.isArray(templateForm?.blocks) ? templateForm.blocks : []),
    [templateForm?.blocks]
  );

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

  const addBlock = (type) => {
    updateBlocks([...blocks, createBlockByType(type)]);
  };

  const removeBlock = (index) => {
    updateBlocks(blocks.filter((_, currentIndex) => currentIndex !== index));
  };

  const updateBlockField = (index, field, value) => {
    updateBlocks(
      blocks.map((block, currentIndex) =>
        currentIndex === index ? { ...block, [field]: value } : block
      )
    );
  };

  const moveBlock = (fromIndex, toIndex) => {
    if (fromIndex === toIndex || fromIndex == null || toIndex == null) return;
    if (toIndex < 0 || toIndex > blocks.length - 1) return;

    const reordered = [...blocks];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);
    updateBlocks(reordered);
  };

  const handleDragStart = (event, index) => {
    setDraggingIndex(index);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (event, index) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  };

  const handleDrop = (event, index) => {
    event.preventDefault();
    moveBlock(draggingIndex, index);
    setDraggingIndex(null);
    setDragOverIndex(null);
  };

  const handleDropAtEnd = (event) => {
    event.preventDefault();
    if (draggingIndex == null) return;
    moveBlock(draggingIndex, blocks.length - 1);
    setDraggingIndex(null);
    setDragOverIndex(null);
  };

  const renderBlockEditor = (block, index) => {
    const type = block?.type || 'text';
    const blockLabel = getBlockLabel(type);
    const isDragTarget = dragOverIndex === index && draggingIndex !== index;

    return (
      <Paper
        key={block._uiId || `${type}-${index}`}
        variant="outlined"
        draggable
        onDragStart={(event) => handleDragStart(event, index)}
        onDragOver={(event) => handleDragOver(event, index)}
        onDrop={(event) => handleDrop(event, index)}
        onDragEnd={() => {
          setDraggingIndex(null);
          setDragOverIndex(null);
        }}
        sx={{
          p: 1.5,
          borderColor: isDragTarget ? theme.palette.primary.main : theme.palette.divider,
          backgroundColor: isDragTarget
            ? alpha(theme.palette.primary.main, 0.08)
            : theme.palette.background.paper,
          cursor: 'grab'
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.25}>
          <Box display="flex" alignItems="center" gap={0.75}>
            <DragIndicatorIcon fontSize="small" color="action" />
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              {blockLabel}
            </Typography>
            <Chip size="small" label={type} />
          </Box>
          <IconButton
            size="small"
            color="error"
            onClick={() => removeBlock(index)}
            disabled={loading}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>

        <Stack spacing={1}>
          {type !== 'page_break' && (
            <TextField
              size="small"
              label="Section Title"
              value={block.title || ''}
              onChange={(event) => updateBlockField(index, 'title', event.target.value)}
            />
          )}

          {type === 'cover' && (
            <>
              <TextField
                size="small"
                label="Subtitle"
                value={block.subtitle || ''}
                onChange={(event) => updateBlockField(index, 'subtitle', event.target.value)}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(block.show_logo)}
                    onChange={(event) =>
                      updateBlockField(index, 'show_logo', event.target.checked)
                    }
                  />
                }
                label="Show logo on cover"
              />
            </>
          )}

          {type === 'chart' && (
            <TextField
              select
              size="small"
              label="Chart Type"
              value={block.chart || 'vulnerability_severity'}
              onChange={(event) => updateBlockField(index, 'chart', event.target.value)}
            >
              {REPORT_CHART_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
          )}

          {type === 'markdown' && (
            <TextField
              select
              size="small"
              label="Markdown Field"
              value={block.field || 'description'}
              onChange={(event) => updateBlockField(index, 'field', event.target.value)}
            >
              {REPORT_MARKDOWN_FIELD_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
          )}

          {type === 'vulnerabilities' && (
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(block.include_descriptions)}
                  onChange={(event) =>
                    updateBlockField(index, 'include_descriptions', event.target.checked)
                  }
                />
              }
              label="Include vulnerability markdown descriptions"
            />
          )}

          {type === 'text' && (
            <TextField
              size="small"
              multiline
              minRows={3}
              label="Content"
              value={block.content || ''}
              onChange={(event) => updateBlockField(index, 'content', event.target.value)}
            />
          )}

          {type === 'page_break' && (
            <Typography variant="caption" color="text.secondary">
              Inserts a hard page break in the generated PDF.
            </Typography>
          )}
        </Stack>
      </Paper>
    );
  };

  return (
    <Card>
      <CardContent>
        <SectionHeader icon={ArticleIcon} title="Report Templates" />

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Drag and drop sections, edit content visually, and preview results live before saving.
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gap: 2,
            gridTemplateColumns: { xs: '1fr', xl: 'minmax(260px, 320px) 1fr' }
          }}
        >
          <Card variant="outlined" sx={{ maxHeight: 700, overflow: 'auto' }}>
            <CardContent>
              <Button
                variant="contained"
                size="small"
                startIcon={<AddIcon />}
                onClick={onCreateNewTemplate}
                disabled={loading}
                sx={{ mb: 1.5 }}
              >
                New Template
              </Button>
              <Divider sx={{ mb: 1 }} />
              {templates.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No report templates found.
                </Typography>
              ) : (
                <List disablePadding>
                  {templates.map((template) => (
                    <ListItem
                      key={template.id}
                      disableGutters
                      sx={{
                        px: 1,
                        py: 0.75,
                        mb: 0.5,
                        borderRadius: 1,
                        backgroundColor:
                          selectedTemplateId === template.id ? 'action.selected' : 'transparent'
                      }}
                      secondaryAction={
                        <Stack direction="row" spacing={0.5}>
                          <Tooltip title="Edit">
                            <IconButton size="small" onClick={() => onSelectTemplate(template)}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          {template.is_system ? (
                            <Tooltip
                              title={
                                template.is_customized ? 'Reset to canonical' : 'Already canonical'
                              }
                            >
                              <span>
                                <IconButton
                                  size="small"
                                  color="warning"
                                  onClick={() => onResetTemplate(template)}
                                  disabled={loading || !template.is_customized}
                                >
                                  <RestartAltIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                          ) : (
                            <Tooltip title="Delete">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => onDeleteTemplate(template.id, template.name)}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Stack>
                      }
                    >
                      <ListItemText
                        primary={template.name}
                        secondary={
                          <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            <Chip
                              size="small"
                              color={template.enabled ? 'success' : 'default'}
                              label={template.enabled ? 'Enabled' : 'Disabled'}
                            />
                            <Chip
                              size="small"
                              color={template.is_system ? 'info' : 'default'}
                              label={template.is_system ? 'System' : 'Custom'}
                            />
                            {template.is_system && template.is_customized && (
                              <Chip size="small" color="warning" label="Customized" />
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                {selectedTemplateId ? 'Visual Template Builder' : 'Create Visual Template'}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Configure branding and placeholders, then arrange report blocks with drag and drop.
              </Typography>

              <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
                {selectedTemplate && (
                  <Chip
                    size="small"
                    color={selectedTemplate.is_system ? 'info' : 'default'}
                    label={selectedTemplate.is_system ? 'System Template' : 'Custom Template'}
                  />
                )}
                {selectedTemplate?.is_system && selectedTemplate?.is_customized && (
                  <Chip size="small" color="warning" label="Customized by Admin" />
                )}
              </Stack>

              <Stack spacing={1.5}>
                <TextField
                  label="Template Key"
                  size="small"
                  value={templateForm.key}
                  onChange={(event) => onChangeTemplateForm('key', event.target.value)}
                  placeholder="manager_executive"
                  disabled={Boolean(selectedTemplate?.is_system)}
                  helperText={
                    selectedTemplate?.is_system
                      ? 'System template keys are locked.'
                      : "Lowercase letters/numbers with '-' or '_'"
                  }
                />
                <TextField
                  label="Display Name"
                  size="small"
                  value={templateForm.name}
                  onChange={(event) => onChangeTemplateForm('name', event.target.value)}
                  placeholder="Manager Executive Report"
                />
                <TextField
                  label="Description"
                  size="small"
                  value={templateForm.description}
                  onChange={(event) => onChangeTemplateForm('description', event.target.value)}
                  placeholder="Executive summary report with risk visuals"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(templateForm.enabled)}
                      onChange={(event) => onChangeTemplateForm('enabled', event.target.checked)}
                    />
                  }
                  label="Template enabled"
                />
              </Stack>

              <Divider sx={{ my: 2 }} />

              <Box
                sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: { xs: '1fr', xl: 'minmax(220px, 260px) 1fr minmax(280px, 340px)' }
                }}
              >
                <Card variant="outlined">
                  <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <PaletteIcon color="primary" fontSize="small" />
                      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                        Block Library
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.25 }}>
                      Add blocks to compose the final PDF structure.
                    </Typography>
                    <Stack spacing={0.75}>
                      {REPORT_BLOCK_LIBRARY.map((item) => (
                        <Button
                          key={item.type}
                          variant="outlined"
                          size="small"
                          onClick={() => addBlock(item.type)}
                          sx={{ justifyContent: 'flex-start', textTransform: 'none' }}
                        >
                          <Box textAlign="left">
                            <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
                              {item.label}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {item.description}
                            </Typography>
                          </Box>
                        </Button>
                      ))}
                    </Stack>
                  </CardContent>
                </Card>

                <Card variant="outlined">
                  <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <ViewCarouselIcon color="primary" fontSize="small" />
                      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                        Drag-and-Drop Canvas
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.25 }}>
                      Reorder blocks by dragging. Each block has tailored options.
                    </Typography>

                    <Stack spacing={1}>
                      {blocks.length === 0 ? (
                        <Paper variant="outlined" sx={{ p: 1.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            No blocks yet. Start by adding one from the block library.
                          </Typography>
                        </Paper>
                      ) : (
                        blocks.map((block, index) => renderBlockEditor(block, index))
                      )}

                      {blocks.length > 0 && (
                        <Paper
                          variant="outlined"
                          onDragOver={(event) => {
                            event.preventDefault();
                            setDragOverIndex(blocks.length);
                          }}
                          onDrop={handleDropAtEnd}
                          sx={{
                            p: 1,
                            borderStyle: 'dashed',
                            borderColor:
                              dragOverIndex === blocks.length
                                ? theme.palette.primary.main
                                : theme.palette.divider,
                            textAlign: 'center',
                            color: 'text.secondary'
                          }}
                        >
                          <Typography variant="caption">Drop block here to move to bottom</Typography>
                        </Paper>
                      )}
                    </Stack>
                  </CardContent>
                </Card>

                <Card variant="outlined">
                  <CardContent>
                    <ReportTemplateLivePreview templateForm={templateForm} />
                  </CardContent>
                </Card>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box
                sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }
                }}
              >
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Branding
                    </Typography>
                    <Stack spacing={1}>
                      <TextField
                        size="small"
                        label="Company Name"
                        value={templateForm.branding?.company_name || ''}
                        onChange={(event) => updateBranding('company_name', event.target.value)}
                      />
                      <TextField
                        size="small"
                        label="Logo URL"
                        value={templateForm.branding?.logo_url || ''}
                        onChange={(event) => updateBranding('logo_url', event.target.value)}
                        placeholder="/pentest/images/<logo>.png"
                      />
                      <Stack direction="row" spacing={1.5}>
                        <TextField
                          size="small"
                          label="Primary Color"
                          type="color"
                          InputLabelProps={{ shrink: true }}
                          value={templateForm.branding?.primary_color || '#0B5CAD'}
                          onChange={(event) => updateBranding('primary_color', event.target.value)}
                          sx={{ minWidth: 130 }}
                        />
                        <TextField
                          size="small"
                          label="Accent Color"
                          type="color"
                          InputLabelProps={{ shrink: true }}
                          value={templateForm.branding?.accent_color || '#1E293B'}
                          onChange={(event) => updateBranding('accent_color', event.target.value)}
                          sx={{ minWidth: 130 }}
                        />
                      </Stack>
                    </Stack>
                  </CardContent>
                </Card>

                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Global Placeholders
                    </Typography>
                    <Stack spacing={1}>
                      <TextField
                        size="small"
                        label="Report Title"
                        value={templateForm.placeholders?.report_title || ''}
                        onChange={(event) => updatePlaceholders('report_title', event.target.value)}
                      />
                      <TextField
                        size="small"
                        label="Report Subtitle"
                        value={templateForm.placeholders?.report_subtitle || ''}
                        onChange={(event) => updatePlaceholders('report_subtitle', event.target.value)}
                      />
                      <TextField
                        size="small"
                        label="Prepared By"
                        value={templateForm.placeholders?.prepared_by || ''}
                        onChange={(event) => updatePlaceholders('prepared_by', event.target.value)}
                      />
                      <TextField
                        size="small"
                        label="Prepared For"
                        value={templateForm.placeholders?.prepared_for || ''}
                        onChange={(event) => updatePlaceholders('prepared_for', event.target.value)}
                      />
                    </Stack>
                  </CardContent>
                </Card>
              </Box>

              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
                Placeholder examples: {'{{record.name}}'}, {'{{record.ip_address}}'}, {'{{pentest.tested_by}}'}, {'{{metrics.vulnerability_count}}'}.
              </Typography>

              <Box display="flex" justifyContent="flex-end" gap={1} sx={{ mt: 1.5 }}>
                {selectedTemplate?.is_system && (
                  <Button
                    variant="outlined"
                    color="warning"
                    startIcon={<RestartAltIcon />}
                    onClick={() => onResetTemplate(selectedTemplate)}
                    disabled={loading || !selectedTemplate.is_customized}
                  >
                    Reset to Canonical
                  </Button>
                )}
                <Button
                  variant="contained"
                  startIcon={<CheckIcon />}
                  onClick={onSaveTemplate}
                  disabled={loading}
                >
                  {selectedTemplateId ? 'Save Changes' : 'Create Template'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ReportTemplatesSection;
