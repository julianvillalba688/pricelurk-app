export function money(value: string | null, currency: string | null): string {
  if (value === null) return 'Sin observación';
  if (!currency) return `${value} (moneda desconocida)`;
  // Preserve large integers and cents without converting the price to a float.
  // The API has already validated/quantized the amount for its currency.
  const [whole, fraction = ''] = value.split('.');
  const formatter = new Intl.NumberFormat('es-CO', { style: 'currency', currency, currencyDisplay: 'code' });
  return formatter.formatToParts(BigInt(whole)).map(part => part.type === 'fraction'
    ? fraction.padEnd(part.value.length, '0').slice(0, part.value.length)
    : part.value).join('');
}
