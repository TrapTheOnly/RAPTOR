import React from 'react';
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
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import {
  Add as AddIcon,
  Article as ArticleIcon,
  Check as CheckIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  RestartAlt as RestartAltIcon
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';

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
}) => (
  <Card>
    <CardContent>
      <SectionHeader icon={ArticleIcon} title="Report Templates" />

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Configure PDF report layout, placeholders, and chart blocks used by pentest records.
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', lg: 'minmax(260px, 320px) 1fr' }
        }}
      >
        <Card variant="outlined" sx={{ maxHeight: 620, overflow: 'auto' }}>
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
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>
              {selectedTemplateId ? 'Edit Report Template' : 'Create Report Template'}
            </Typography>

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
                placeholder="Report with executive summary and risk charts"
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

              <TextField
                label="Template JSON"
                multiline
                minRows={18}
                value={templateForm.templateJson}
                onChange={(event) => onChangeTemplateForm('templateJson', event.target.value)}
                helperText="Blocks support: cover, engagement_overview, key_metrics, chart, open_ports, markdown, checklists, vulnerabilities, text, page_break."
              />

              <Typography variant="caption" color="text.secondary">
                Common placeholders: {'{{record.name}}'}, {'{{record.ip_address}}'}, {'{{pentest.tested_by}}'}, {'{{metrics.vulnerability_count}}'}.
              </Typography>

              <Box display="flex" justifyContent="flex-end" gap={1}>
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
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </CardContent>
  </Card>
);

export default ReportTemplatesSection;
