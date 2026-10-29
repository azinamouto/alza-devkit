export type CustomField = {
  name: string;
  label: string;
  type: string;
  required: boolean;
  unique: boolean;
  default?: string | number | boolean | null;
  null_probability: number;
  options: Record<string, string | number | string[] | number[] | null>;
  computed?: { operation: "multiply" | "age" | "full_name"; sources: string[]; reference_date?: string } | null;
};

export type Template = {
  id?: string;
  name: string;
  description: string;
  version: 1;
  locale: string;
  fields: CustomField[];
};

export type CustomRequest = {
  template: Template;
  count: number;
  seed: number;
};

export type CustomDataset = {
  total_records: number;
  seed: number;
  fields: string[];
  data: Record<string, string | number | boolean | null>[];
};

export type FieldOptions = {
  min?: number;
  max?: number;
  precision?: number;
  min_length?: number;
  max_length?: number;
  prefix?: string;
  suffix?: string;
  values?: string[];
  weights?: number[];
  min_date?: string;
  max_date?: string;
  format?: string;
  start?: number;
  step?: number;
  padding?: number;
};

export const newField = (name = "field_1", type = "string"): CustomField => ({ name, label: "", type, required: true, unique: false, null_probability: 0, options: {} });
export const presets: Template[] = [
  { name: "Student Enrollment", description: "Synthetic student records", version: 1, locale: "en_PH", fields: [
    { ...newField("student_id", "student_id"), unique: true, options: { prefix: "STU-", start: 1, step: 1, padding: 5 } },
    newField("student_name", "full_name"),
    { ...newField("grade_level", "enum"), options: { values: ["Grade 7", "Grade 8", "Grade 9", "Grade 10"] } },
    newField("enrollment_date", "date"),
  ] },
  { name: "Sample Transactions", description: "Synthetic product transactions", version: 1, locale: "en_PH", fields: [
    newField("transaction_id", "transaction_id"), newField("product", "product_name"),
    { ...newField("quantity", "quantity"), options: { min: 1, max: 20 } },
    { ...newField("unit_price", "price"), options: { min: 1, max: 1000, precision: 2 } },
    { ...newField("total_amount", "computed"), computed: { operation: "multiply", sources: ["quantity", "unit_price"] } },
  ] },
];
