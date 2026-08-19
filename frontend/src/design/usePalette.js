import { useTheme } from '@mui/material/styles';
import { getPalette } from './tokens';

export const usePalette = () => {
  const theme = useTheme();
  return theme.raptor || getPalette(theme.palette.mode);
};
