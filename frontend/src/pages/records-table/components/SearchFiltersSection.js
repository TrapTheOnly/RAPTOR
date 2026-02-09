import React from 'react';
import {
  alpha,
  Box,
  Button,
  Chip,
  IconButton,
  InputAdornment,
  Menu,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import {
  Add,
  ArrowDropDown,
  Download,
  Refresh,
  Search
} from '@mui/icons-material';

const SearchFiltersSection = ({
  activeFilters,
  searchQuery,
  searchInput,
  dropdownOpen,
  suggestions,
  canExportRecords,
  onClearAllFilters,
  onRemoveFilter,
  onSetSearchQuery,
  onSetSearchInput,
  onInputChange,
  onSubmitSearch,
  onSelectSuggestion,
  onSetDropdownOpen,
  onExportCsv,
  onRefresh,
  onOpenSearchMenu,
  searchMenuAnchor,
  selectedParameter,
  onCloseSearchMenu,
  searchParameters,
  parameterValues,
  parameterCounts,
  onSelectParameter,
  onAddFilter,
  onBackToParameters,
  theme
}) => (
  <Box mb={3}>
    {(activeFilters.length > 0 || searchQuery) && (
      <Box mb={2}>
        <Box display="flex" alignItems="center" gap={1} mb={1}>
          <Typography variant="body2" color="text.secondary">
            Active Filters:
          </Typography>
          <Button size="small" onClick={onClearAllFilters} sx={{ minWidth: 'auto', p: 0.5 }}>
            Clear All
          </Button>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {activeFilters.map((filter) => (
            <Chip
              key={filter.id}
              label={filter.label}
              onDelete={() => onRemoveFilter(filter.id)}
              size="small"
              icon={
                filter.hasWildcards ? <Typography sx={{ fontSize: '0.8em' }}>*</Typography> : undefined
              }
              sx={{
                backgroundColor: filter.hasWildcards
                  ? alpha(theme.palette.warning.main, 0.1)
                  : alpha(theme.palette.primary.main, 0.1),
                color: filter.hasWildcards
                  ? theme.palette.warning.main
                  : theme.palette.primary.main,
                '& .MuiChip-deleteIcon': {
                  color: filter.hasWildcards
                    ? theme.palette.warning.main
                    : theme.palette.primary.main
                }
              }}
            />
          ))}

          {searchQuery && (
            <Chip
              label={`Search: "${searchQuery}"`}
              onDelete={() => {
                onSetSearchQuery('');
                onSetSearchInput('');
              }}
              size="small"
              sx={{
                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                color: theme.palette.secondary.main,
                '& .MuiChip-deleteIcon': {
                  color: theme.palette.secondary.main
                }
              }}
            />
          )}
        </Stack>
      </Box>
    )}

    <Box display="flex" gap={1} position="relative">
      <Box position="relative" width="100%">
        <TextField
          fullWidth
          value={searchInput}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              if (dropdownOpen && suggestions.length > 0) {
                onSelectSuggestion(suggestions[0]);
              } else {
                onSubmitSearch();
              }
            } else if (event.key === 'Tab' && dropdownOpen && suggestions.length > 0) {
              event.preventDefault();
              onSelectSuggestion(suggestions[0]);
            } else if (event.key === 'Escape') {
              onSetDropdownOpen(false);
            } else if (event.key === 'ArrowDown' && dropdownOpen) {
              event.preventDefault();
            }
          }}
          placeholder="Type field=value (e.g., source=Prod*) or search text..."
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search color="action" />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                {canExportRecords && (
                  <Tooltip title="Export Filtered Results">
                    <IconButton onClick={onExportCsv} size="small">
                      <Download />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="Refresh">
                  <IconButton onClick={onRefresh} size="small">
                    <Refresh />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            )
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              backgroundColor: 'background.paper',
              '& fieldset': {
                border: `1px solid ${theme.palette.divider}`
              }
            }
          }}
        />

        {dropdownOpen && suggestions.length > 0 && (
          <Paper
            sx={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              zIndex: 1300,
              mt: 0.5,
              maxHeight: 300,
              overflow: 'auto',
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: 1,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
            }}
          >
            {suggestions.map((suggestion, index) => (
              <Box
                key={index}
                onClick={() => onSelectSuggestion(suggestion)}
                sx={{
                  p: 1.5,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.08)
                  },
                  borderBottom:
                    index < suggestions.length - 1
                      ? `1px solid ${alpha(theme.palette.divider, 0.5)}`
                      : 'none'
                }}
              >
                <Box display="flex" alignItems="center" flex={1}>
                  {suggestion.icon && (
                    <Typography sx={{ fontSize: '1.1em', mr: 1.5 }}>{suggestion.icon}</Typography>
                  )}
                  <Box>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 500,
                        fontFamily:
                          suggestion.type === 'value' &&
                          (suggestion.field === 'ip' || suggestion.field === 'ports')
                            ? 'monospace'
                            : 'inherit'
                      }}
                    >
                      {suggestion.display}
                    </Typography>
                    {suggestion.description && (
                      <Typography variant="caption" color="text.secondary">
                        {suggestion.description}
                      </Typography>
                    )}
                    {suggestion.type === 'value' && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        Use * for wildcards (e.g., {suggestion.value}*)
                      </Typography>
                    )}
                  </Box>
                </Box>
                {suggestion.count !== undefined && (
                  <Chip
                    label={suggestion.count}
                    size="small"
                    sx={{
                      height: 18,
                      fontSize: '0.65rem',
                      backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      color: theme.palette.primary.main
                    }}
                  />
                )}
              </Box>
            ))}
          </Paper>
        )}
      </Box>

      <Button
        variant="contained"
        startIcon={<Add />}
        endIcon={<ArrowDropDown />}
        onClick={onOpenSearchMenu}
        sx={{
          minWidth: 'auto',
          whiteSpace: 'nowrap',
          backgroundColor: 'background.paper',
          color: 'text.primary',
          border: `1px solid ${theme.palette.divider}`,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          '&:hover': {
            backgroundColor: alpha(theme.palette.primary.main, 0.04),
            borderColor: theme.palette.primary.main,
            boxShadow: '0 4px 8px rgba(0,0,0,0.15)'
          },
          '&:active': {
            backgroundColor: alpha(theme.palette.primary.main, 0.08)
          },
          px: 2,
          py: 1,
          fontWeight: 500,
          textTransform: 'none'
        }}
      >
        Add Filter
      </Button>

      <Tooltip
        title={
          <Box>
            <Typography variant="caption" display="block" sx={{ fontWeight: 500 }}>
              Smart Search Examples:
            </Typography>
            <Typography variant="caption" display="block">
              • source=Production (or src=Production)
            </Typography>
            <Typography variant="caption" display="block">
              • open_ports=443 (or port=443)
            </Typography>
            <Typography variant="caption" display="block">
              • status=updated (or state=updated)
            </Typography>
            <Typography variant="caption" display="block">
              • owner=john (or app_owner=john)
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1, fontWeight: 500 }}>
              Wildcards:
            </Typography>
            <Typography variant="caption" display="block">
              • domain=*.example.com (ends with)
            </Typography>
            <Typography variant="caption" display="block">
              • source=Prod* (starts with)
            </Typography>
            <Typography variant="caption" display="block">
              • owner=*john* (contains)
            </Typography>
            <Typography variant="caption" display="block">
              • port=80? (single character)
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1, fontStyle: 'italic' }}>
              Or just type any text to search all fields
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1, opacity: 0.7 }}>
              💡 Press Tab to accept suggestions, Enter to search
            </Typography>
          </Box>
        }
        arrow
        placement="bottom-start"
      >
        <IconButton size="small" sx={{ color: 'text.secondary' }}>
          <Typography variant="caption" sx={{ fontSize: '1.2em' }}>
            💡
          </Typography>
        </IconButton>
      </Tooltip>
    </Box>

    <Menu
      anchorEl={searchMenuAnchor}
      open={Boolean(searchMenuAnchor)}
      onClose={onCloseSearchMenu}
      transformOrigin={{ horizontal: 'right', vertical: 'top' }}
      anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      PaperProps={{
        elevation: 4,
        sx: {
          maxWidth: 320,
          mt: 0.5,
          backgroundColor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 1.5,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          '& .MuiMenuItem-root': {
            py: 1,
            px: 1.5,
            mx: 0.5,
            my: 0.25,
            borderRadius: 0.75,
            fontSize: '0.875rem',
            transition: 'all 0.15s ease-in-out',
            '&:hover': {
              backgroundColor: alpha(theme.palette.primary.main, 0.06),
              transform: 'translateX(1px)'
            },
            '&:first-of-type': {
              mt: 0.5
            },
            '&:last-of-type': {
              mb: 0.5
            }
          },
          '& .MuiList-root': {
            py: 0
          }
        }
      }}
    >
      {!selectedParameter ? (
        searchParameters.map((parameter) => (
          <MenuItem
            key={parameter.key}
            onClick={() => onSelectParameter(parameter)}
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1.5,
              backgroundColor: 'background.default',
              border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
              mb: 0.5,
              borderRadius: 1,
              py: 1.25,
              px: 1.5,
              fontSize: '0.875rem',
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.04),
                borderColor: alpha(theme.palette.primary.main, 0.2),
                transform: 'translateX(2px)',
                boxShadow: '0 2px 6px rgba(0,0,0,0.08)'
              },
              '&:last-child': {
                mb: 0
              }
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 32,
                height: 32,
                borderRadius: 1,
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                flexShrink: 0
              }}
            >
              <Typography sx={{ fontSize: '1.1em' }}>{parameter.icon}</Typography>
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  color: 'text.primary',
                  mb: 0.25,
                  fontSize: '0.875rem'
                }}
              >
                {parameter.label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: 'text.secondary',
                  mb: 0.75,
                  lineHeight: 1.3,
                  fontSize: '0.75rem'
                }}
              >
                {parameter.description}
              </Typography>
              <Chip
                label={`${parameterValues[parameter.key]?.length || 0} ${
                  parameter.key === 'ports' ? 'ports' : 'values'
                }`}
                size="small"
                sx={{
                  height: 18,
                  fontSize: '0.65rem',
                  backgroundColor: alpha(theme.palette.info.main, 0.08),
                  color: 'info.main',
                  fontWeight: 500,
                  '& .MuiChip-label': {
                    px: 0.75
                  }
                }}
              />
            </Box>
          </MenuItem>
        ))
      ) : (
        <>
          <MenuItem
            onClick={onBackToParameters}
            sx={{
              borderBottom: `1px solid ${theme.palette.divider}`,
              mb: 0.5,
              backgroundColor: alpha(theme.palette.secondary.main, 0.04),
              '&:hover': {
                backgroundColor: alpha(theme.palette.secondary.main, 0.08),
                transform: 'translateX(0px)'
              },
              mx: 0,
              px: 1.5,
              py: 1,
              borderRadius: '6px 6px 0 0'
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography
                variant="body2"
                sx={{
                  color: 'secondary.main',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: '0.875rem'
                }}
              >
                ← Back to Parameters
              </Typography>
            </Box>
          </MenuItem>
          <Box sx={{ px: 1.5, pb: 0.75, pt: 0.25 }}>
            <Typography
              variant="body2"
              sx={{
                color: 'text.primary',
                fontWeight: 600,
                mb: 0.25,
                fontSize: '0.875rem'
              }}
            >
              {selectedParameter.label} Values ({parameterValues[selectedParameter.key]?.length || 0}
              ):
            </Typography>
            {selectedParameter.key === 'ports' && (
              <Typography
                variant="caption"
                sx={{
                  color: 'text.secondary',
                  fontStyle: 'italic',
                  fontSize: '0.7rem'
                }}
              >
                Individual ports from all records
              </Typography>
            )}
          </Box>
          {parameterValues[selectedParameter.key]?.map((value) => (
            <MenuItem
              key={value}
              onClick={() => onAddFilter(selectedParameter.key, value)}
              sx={{
                ml: 0.5,
                mr: 0.5,
                mb: 0.5,
                borderRadius: 0.75,
                fontFamily:
                  selectedParameter.key === 'ip' || selectedParameter.key === 'ports'
                    ? 'monospace'
                    : 'inherit',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                backgroundColor: 'background.default',
                border: `1px solid ${alpha(theme.palette.divider, 0.25)}`,
                py: 1,
                px: 1.5,
                fontSize: '0.875rem',
                transition: 'all 0.15s ease-in-out',
                '&:hover': {
                  backgroundColor: alpha(theme.palette.success.main, 0.06),
                  borderColor: alpha(theme.palette.success.main, 0.25),
                  transform: 'translateX(1px)',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.08)'
                },
                '&:last-child': {
                  mb: 0
                }
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 500,
                  color: 'text.primary',
                  fontSize: '0.875rem'
                }}
              >
                {value}
              </Typography>
              <Chip
                label={parameterCounts[selectedParameter.key]?.[value] || 0}
                size="small"
                sx={{
                  ml: 1,
                  height: 16,
                  fontSize: '0.6rem',
                  backgroundColor: alpha(theme.palette.success.main, 0.08),
                  color: 'success.main',
                  fontWeight: 600,
                  '& .MuiChip-label': {
                    px: 0.5
                  }
                }}
              />
            </MenuItem>
          ))}
        </>
      )}
    </Menu>
  </Box>
);

export default SearchFiltersSection;
