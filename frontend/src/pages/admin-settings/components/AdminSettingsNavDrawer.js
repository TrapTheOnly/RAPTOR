import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Collapse,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon
} from '@mui/icons-material';
import { DRAWER_WIDTH } from '../constants';

const AdminSettingsNavDrawer = ({
  isMobile,
  navOpen,
  onClose,
  sections,
  selectedSection,
  onSelectSection,
  userManagementPage,
  onSelectUserManagementPage,
  reportTemplates,
  selectedReportTemplateId,
  onCreateReportTemplate,
  onSelectReportTemplate
}) => {
  const theme = useTheme();
  const [usersNavOpen, setUsersNavOpen] = useState(selectedSection === 'users');
  const [reportTemplatesNavOpen, setReportTemplatesNavOpen] = useState(
    selectedSection === 'report-templates'
  );

  const userSubSections = useMemo(
    () => [
      { key: 'existing', label: 'Existing Users' },
      { key: 'add-domain', label: 'Add LDAP Users' },
      { key: 'local', label: 'Add Local Users' }
    ],
    []
  );

  useEffect(() => {
    if (selectedSection === 'users') {
      setUsersNavOpen(true);
    }
  }, [selectedSection]);

  useEffect(() => {
    if (selectedSection === 'report-templates') {
      setReportTemplatesNavOpen(true);
    }
  }, [selectedSection]);

  const handleUsersSectionClick = () => {
    if (selectedSection !== 'users') {
      onSelectSection('users');
      setUsersNavOpen(true);
      return;
    }
    setUsersNavOpen((prev) => !prev);
  };

  const handleUsersSubSectionClick = (subSectionKey) => {
    onSelectUserManagementPage(subSectionKey);
    onSelectSection('users');
  };

  const handleReportTemplatesSectionClick = () => {
    if (selectedSection !== 'report-templates') {
      onSelectSection('report-templates');
      setReportTemplatesNavOpen(true);
      return;
    }
    setReportTemplatesNavOpen((prev) => !prev);
  };

  const handleCreateTemplateClick = () => {
    onCreateReportTemplate();
    onSelectSection('report-templates');
  };

  const handleSelectTemplateClick = (template) => {
    onSelectReportTemplate(template);
    onSelectSection('report-templates');
  };

  return (
    <Drawer
      variant={isMobile ? 'temporary' : 'permanent'}
      open={isMobile ? navOpen : true}
      onClose={onClose}
      ModalProps={{ keepMounted: true }}
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: DRAWER_WIDTH,
          boxSizing: 'border-box',
          borderRight: `1px solid ${theme.palette.divider}`
        }
      }}
    >
      <Box sx={{ width: DRAWER_WIDTH }}>
        <Box sx={theme.mixins.toolbar} />
        <Box sx={{ px: 2.5, py: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Admin Settings
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Select a section to manage
          </Typography>
        </Box>
        <Divider />
        <List sx={{ px: 1 }}>
          {sections.map((section) => {
            const isUsersSection = section.key === 'users';
            const isReportTemplatesSection = section.key === 'report-templates';
            const isSelected = selectedSection === section.key;

            return (
              <Box key={section.key}>
                <ListItemButton
                  selected={isSelected}
                  onClick={
                    isUsersSection
                      ? handleUsersSectionClick
                      : isReportTemplatesSection
                      ? handleReportTemplatesSectionClick
                      : () => onSelectSection(section.key)
                  }
                  sx={{
                    borderRadius: 1,
                    mb: 0.5,
                    '&.Mui-selected': {
                      backgroundColor: alpha(theme.palette.primary.main, 0.12)
                    },
                    '&.Mui-selected:hover': {
                      backgroundColor: alpha(theme.palette.primary.main, 0.18)
                    }
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    <section.icon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={section.label}
                    primaryTypographyProps={{ fontSize: '0.95rem', fontWeight: 600 }}
                  />
                  {isUsersSection &&
                    (usersNavOpen ? (
                      <ExpandLessIcon fontSize="small" />
                    ) : (
                      <ExpandMoreIcon fontSize="small" />
                    ))}
                  {isReportTemplatesSection &&
                    (reportTemplatesNavOpen ? (
                      <ExpandLessIcon fontSize="small" />
                    ) : (
                      <ExpandMoreIcon fontSize="small" />
                    ))}
                </ListItemButton>

                {isUsersSection && (
                  <Collapse in={usersNavOpen} timeout="auto" unmountOnExit>
                    <List dense disablePadding sx={{ pl: 5, pr: 0.5, pb: 0.5 }}>
                      {userSubSections.map((subSection) => (
                        <ListItemButton
                          key={subSection.key}
                          selected={
                            selectedSection === 'users' &&
                            userManagementPage === subSection.key
                          }
                          onClick={() => handleUsersSubSectionClick(subSection.key)}
                          sx={{
                            borderRadius: 1,
                            minHeight: 34,
                            mb: 0.25,
                            '&.Mui-selected': {
                              backgroundColor: alpha(theme.palette.primary.main, 0.16)
                            },
                            '&.Mui-selected:hover': {
                              backgroundColor: alpha(theme.palette.primary.main, 0.2)
                            }
                          }}
                        >
                          <ListItemText
                            primary={subSection.label}
                            primaryTypographyProps={{
                              fontSize: '0.85rem',
                              fontWeight: 500
                            }}
                          />
                        </ListItemButton>
                      ))}
                    </List>
                  </Collapse>
                )}

                {isReportTemplatesSection && (
                  <Collapse in={reportTemplatesNavOpen} timeout="auto" unmountOnExit>
                    <List
                      dense
                      disablePadding
                      sx={{
                        pl: 5,
                        pr: 0.5,
                        pb: 0.5,
                        maxHeight: 280,
                        overflowY: 'auto'
                      }}
                    >
                      <ListItemButton
                        selected={
                          selectedSection === 'report-templates' &&
                          !selectedReportTemplateId
                        }
                        onClick={handleCreateTemplateClick}
                        sx={{
                          borderRadius: 1,
                          minHeight: 34,
                          mb: 0.25,
                          '&.Mui-selected': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.16)
                          },
                          '&.Mui-selected:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.2)
                          }
                        }}
                      >
                        <ListItemText
                          primary="New Template"
                          primaryTypographyProps={{
                            fontSize: '0.84rem',
                            fontWeight: 600
                          }}
                        />
                      </ListItemButton>

                      {(reportTemplates || []).map((template) => (
                        <ListItemButton
                          key={template.id}
                          selected={
                            selectedSection === 'report-templates' &&
                            selectedReportTemplateId === template.id
                          }
                          onClick={() => handleSelectTemplateClick(template)}
                          sx={{
                            borderRadius: 1,
                            minHeight: 34,
                            mb: 0.25,
                            '&.Mui-selected': {
                              backgroundColor: alpha(theme.palette.primary.main, 0.16)
                            },
                            '&.Mui-selected:hover': {
                              backgroundColor: alpha(theme.palette.primary.main, 0.2)
                            }
                          }}
                        >
                          <ListItemText
                            primary={template.name}
                            secondary={template.enabled ? null : 'Disabled'}
                            primaryTypographyProps={{
                              fontSize: '0.82rem',
                              fontWeight: 500,
                              noWrap: true
                            }}
                            secondaryTypographyProps={{
                              fontSize: '0.72rem'
                            }}
                          />
                        </ListItemButton>
                      ))}
                    </List>
                  </Collapse>
                )}
              </Box>
            );
          })}
        </List>
      </Box>
    </Drawer>
  );
};

export default AdminSettingsNavDrawer;
