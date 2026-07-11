import type { TextInputProps } from 'react-native';

import { TextField } from '@/design-system';

interface FormFieldProps extends TextInputProps {
  label: string;
  error?: string;
}

export function FormField(props: FormFieldProps) {
  return <TextField {...props} />;
}
