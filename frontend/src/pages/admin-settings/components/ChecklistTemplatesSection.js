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
  Check as CheckIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  FactCheck as FactCheckIcon,
  RestartAlt as RestartAltIcon
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';

const ChecklistTemplatesSection = ({
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
      <SectionHeader icon={FactCheckIcon} title="Checklist Templates" />

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Manage service checklists used in pentest records. Auto-enable ports are applied when matching open ports are added.
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
                No checklist templates found.
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
                        selectedTemplateId === template.id
                          ? 'action.selected'
                          : 'transparent'
                    }}
                    secondaryAction={
                      <Stack direction="row" spacing={0.5}>
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => onSelectTemplate(template)}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {template.is_system ? (
                          <Tooltip
                            title={
                              template.is_customized
                                ? 'Reset to canonical'
                                : 'Already canonical'
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
                          <Chip size="small" label={template.service || 'service'} />
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
              {selectedTemplateId ? 'Edit Template' : 'Create Template'}
            </Typography>
            {selectedTemplate && (
              <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
                <Chip
                  size="small"
                  color={selectedTemplate.is_system ? 'info' : 'default'}
                  label={selectedTemplate.is_system ? 'System Template' : 'Custom Template'}
                />
                {selectedTemplate.is_system && selectedTemplate.is_customized && (
                  <Chip size="small" color="warning" label="Customized by Admin" />
                )}
                {selectedTemplate.system_revision && (
                  <Chip
                    size="small"
                    variant="outlined"
                    label={`Revision ${selectedTemplate.system_revision.slice(0, 8)}`}
                  />
                )}
              </Stack>
            )}

            <Stack spacing={1.5}>
              <TextField
                label="Template Key"
                size="small"
                value={templateForm.key}
                onChange={(event) => onChangeTemplateForm('key', event.target.value)}
                placeholder="smtp-security"
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
                placeholder="SMTP Security Checklist"
              />
              <TextField
                label="Service"
                size="small"
                value={templateForm.service}
                onChange={(event) => onChangeTemplateForm('service', event.target.value)}
                placeholder="smtp"
              />
              <TextField
                label="Source"
                size="small"
                value={templateForm.source}
                onChange={(event) => onChangeTemplateForm('source', event.target.value)}
                placeholder="OWASP ASVS + CIS"
              />
              <TextField
                label="Auto-enable ports"
                size="small"
                value={templateForm.autoPortsText}
                onChange={(event) => onChangeTemplateForm('autoPortsText', event.target.value)}
                placeholder="25, 465, 587"
                helperText="Comma-separated TCP/UDP ports"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(templateForm.enabled)}
                    onChange={(event) =>
                      onChangeTemplateForm('enabled', event.target.checked)
                    }
                  />
                }
                label="Template enabled"
              />

              <TextField
                label="Sections JSON"
                multiline
                minRows={14}
                value={templateForm.sectionsJson}
                onChange={(event) =>
                  onChangeTemplateForm('sectionsJson', event.target.value)
                }
                helperText='Expected format: [{"name":"...","items":[{"id":"...","testName":"...","description":"...","tools":"..."}]}]'
              />

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

export default ChecklistTemplatesSection;
