import { Input } from "antd";

export default function JsonEditor({
  value,
  onChange,
  rows = 8,
  placeholder
}: {
  value?: string;
  onChange?: (value: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <Input.TextArea
      className="json-editor"
      rows={rows}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
      placeholder={placeholder || '{\n  "type": "object",\n  "properties": {}\n}'}
    />
  );
}

