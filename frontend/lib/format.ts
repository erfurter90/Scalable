// Intl.NumberFormat's "currency" style silently rounds to 2 fraction digits for any
// syntactically-valid 3-letter code, real or not — so a value entered directly in a crypto
// unit (currency="BTC") would visually round away almost all of its precision. Known fiat
// codes keep the normal 2-decimal currency display; anything else is shown as a plain,
// full-precision number with the code as a suffix.
const FIAT_CURRENCIES = new Set(["EUR", "USD", "GBP", "CHF", "JPY"]);

export function formatCurrency(value: string | number, currency = "EUR"): string {
  const num = typeof value === "string" ? Number(value) : value;

  if (FIAT_CURRENCIES.has(currency.toUpperCase())) {
    return new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(num);
  }

  const precise = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 8 }).format(num);
  return `${precise} ${currency}`;
}

export function formatPercent(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
    new Date(iso)
  );
}
