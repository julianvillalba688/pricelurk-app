export function money(value: string | null, currency: string | null): string {
  if (value === null) return 'Sin observación';
  if (!currency) return `${value} (moneda desconocida)`;
  // Conversion is for display/charting only. All calculations remain decimal on the API.
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency, currencyDisplay: 'code' }).format(Number(value));
}
