import React from 'react';
import { Autocomplete, TextField } from '@mui/material';
import { TYPE } from '../tokens';
import { usePalette } from '../usePalette';
import { Text } from './type';

const isEnumOption = (option) =>
  option != null &&
  typeof option === 'object' &&
  Object.prototype.hasOwnProperty.call(option, 'value') &&
  Object.prototype.hasOwnProperty.call(option, 'label');

const isPrimitive = (value) => value == null || typeof value === 'string' || typeof value === 'number';

/**
 * The one dropdown. Autocomplete (Popper) — never MUI Select, whose Menu uses
 * the dialog backdrop and tints the whole screen.
 *
 * Enum mode: pass `{ value, label }[]` and a primitive `value`; `onChange`
 * receives the primitive.
 * Entity mode: pass objects plus `getOptionLabel`; `onChange` receives the
 * object (or array, if `multiple`).
 */
export const Combo = ({
  label,
  hint,
  options = [],
  value,
  onChange,
  multiple = false,
  placeholder,
  getOptionLabel,
  renderOption,
  disabled = false,
  fullWidth = true,
  style,
  disableClearable,
  mode,
  ...rest
}) => {
  const palette = usePalette();
  const enumMode =
    mode === 'enum' ||
    (mode !== 'entity' &&
      (options.length > 0
        ? isEnumOption(options[0])
        : multiple
          ? Array.isArray(value) && value.every(isPrimitive)
          : isPrimitive(value)));

  const readLabel =
    getOptionLabel ||
    ((option) => {
      if (option == null) return '';
      if (isEnumOption(option)) return option.label;
      if (typeof option === 'object') return String(option.name || option.title || option.label || '');
      return String(option);
    });

  const selected = enumMode
    ? multiple
      ? (Array.isArray(value) ? value : []).map(
          (item) => options.find((option) => option.value === item) || { value: item, label: String(item) }
        )
      : options.find((option) => option.value === value) ||
        (value === '' || value == null ? null : { value, label: String(value) })
    : value;

  const unwrap = (item) => {
    if (item == null) return multiple ? [] : '';
    if (isEnumOption(item)) return item.value;
    return item;
  };

  const handleChange = (_event, next) => {
    if (!onChange) return;
    if (enumMode) {
      onChange(multiple ? (next || []).map(unwrap) : unwrap(next));
      return;
    }
    onChange(next);
  };

  return (
    <label
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minWidth: 0,
        width: fullWidth ? '100%' : undefined,
        ...style
      }}
    >
      {label ? <span style={{ ...TYPE.micro, color: palette.textTertiary }}>{label}</span> : null}
      <Autocomplete
        options={options}
        value={selected}
        multiple={multiple}
        disabled={disabled}
        disableClearable={disableClearable ?? (!multiple && enumMode)}
        getOptionLabel={readLabel}
        isOptionEqualToValue={(a, b) => {
          if (a === b) return true;
          if (enumMode) return a?.value === b?.value;
          if (isPrimitive(a) && isPrimitive(b)) return String(a) === String(b);
          if (a?.id != null && b?.id != null) return a.id === b.id;
          return false;
        }}
        onChange={handleChange}
        renderOption={renderOption}
        size="small"
        filterSelectedOptions={multiple}
        slotProps={{
          popper: {
            placement: 'bottom-start',
            modifiers: [{ name: 'flip', enabled: false }]
          }
        }}
        ListboxProps={{ style: { maxHeight: 280 } }}
        sx={
          multiple
            ? {
                '& .MuiOutlinedInput-root': {
                  height: 'auto',
                  minHeight: 32,
                  flexWrap: 'wrap',
                  py: '3px'
                }
              }
            : {
                '& .MuiOutlinedInput-root': { height: 32 }
              }
        }
        renderInput={(params) => <TextField {...params} size="small" placeholder={placeholder} />}
        {...rest}
      />
      {hint ? (
        <Text as="span" variant="meta" tone="secondary">
          {hint}
        </Text>
      ) : null}
    </label>
  );
};
