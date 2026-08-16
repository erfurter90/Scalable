// Mirrors backend/app/schemas/*.py. Decimal fields are serialized by the backend as JSON
// strings (e.g. "1234.50") to avoid floating-point rounding of money values; float fields
// (percentages, scores) come through as JSON numbers.

export type EntryType = "income" | "expense" | "asset" | "liability";
export type AssetSubcategory = "cash" | "btc" | "crypto" | "stocks" | "etf" | "other";
export type DataPointStatus = "ok" | "unavailable" | "error";
export type PurchaseCurrency = "EUR" | "USD";

export interface User {
  id: number;
  username: string;
}

export interface FinancialEntry {
  id: number;
  entry_type: EntryType;
  category: string;
  subcategory: string | null;
  label: string;
  amount: string;
  // Set together when the entry's value is derived from a quantity ("0.2 BTC") rather than a
  // manually typed EUR figure — the backend computes `amount` from these at the current price.
  quantity: string | null;
  price_asset_id: string | null;
  // Weighted-average acquisition price per unit, always in EUR. Null until a purchase price
  // has been recorded at least once (on creation or via a "Nachkauf").
  average_cost_basis: string | null;
  currency: string;
  snapshot_date: string;
  notes: string | null;
  // "manual" (typed in by hand) or "bitvavo" (written by the Bitvavo sync — see useBitvavo.ts).
  source: string;
}

export interface FinancialEntryCreate {
  entry_type: EntryType;
  category: string;
  subcategory?: string | null;
  label: string;
  // Either `amount`, or both `quantity` and `price_asset_id`, must be provided.
  amount?: string;
  quantity?: string;
  price_asset_id?: string;
  // Optional: seeds average_cost_basis. Only valid together with quantity/price_asset_id.
  purchase_price?: string;
  purchase_price_currency?: PurchaseCurrency;
  currency?: string;
  snapshot_date: string;
  notes?: string | null;
}

export interface PurchaseCreate {
  additional_quantity: string;
  purchase_price: string;
  purchase_price_currency: PurchaseCurrency;
}

export interface CostBasisSet {
  purchase_price: string;
  purchase_price_currency: PurchaseCurrency;
}

export interface FinancialEntryUpdate {
  category?: string;
  subcategory?: string | null;
  label?: string;
  amount?: string;
  // Explicit `null` clears quantity-tracking (e.g. switching an entry back to a manually
  // typed amount); omitting the key entirely leaves the current value untouched.
  quantity?: string | null;
  price_asset_id?: string | null;
  currency?: string;
  snapshot_date?: string;
  notes?: string | null;
}

export interface NetWorthSnapshot {
  snapshot_date: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  cash_total: string;
  investments_total: string;
}

export interface NetWorthChange {
  net_worth_start: number;
  net_worth_end: number;
  change_abs: number;
  change_pct: number | null;
  period_start: string;
  period_end: string;
}

export interface AllocationItem {
  subcategory: string;
  amount: string;
  percent_of_total: number;
}

export interface PortfolioAllocation {
  snapshot_date: string;
  total_assets: string;
  breakdown: AllocationItem[];
  btc_percent_of_assets: number;
  btc_percent_of_investments: number;
}

export interface CryptoAllocationItem {
  coin: string; // CoinGecko coin id when known, otherwise the entry's label
  amount: string;
  percent_of_crypto: number;
}

export interface CryptoBreakdown {
  snapshot_date: string;
  total_crypto: string;
  breakdown: CryptoAllocationItem[];
}

export interface MarketDataPoint {
  metric: string;
  value: number | null;
  unit: string | null;
  status: DataPointStatus;
  source: string;
  source_endpoint: string | null;
  fetched_at: string;
  as_of: string | null;
  error_message: string | null;
}

export interface BtcPrice {
  usd: MarketDataPoint;
  eur: MarketDataPoint;
  change_24h: MarketDataPoint;
  change_7d: MarketDataPoint;
  change_30d: MarketDataPoint;
}

export interface FearGreed {
  index: MarketDataPoint;
}

export interface MarketSnapshot {
  btc: BtcPrice;
  fear_greed: FearGreed;
}

export interface SubScore {
  name: string;
  value: number | null;
  status: "ok" | "unavailable";
  unavailable_reason: string | null;
  inputs: Record<string, unknown>;
  weight_declared: number;
  weight_used: number | null;
}

export interface Score {
  score_date: string;
  total_score: number | null;
  weights_config_version: number;
  subscores: SubScore[];
}

export interface Dashboard {
  net_worth: NetWorthSnapshot | null;
  net_worth_change_30d: NetWorthChange | null;
  portfolio: PortfolioAllocation | null;
  crypto_breakdown: CryptoBreakdown | null;
  market: MarketSnapshot;
  score: Score;
}

export interface ChatResponse {
  ai_available: boolean;
  reply: string | null;
  data_used: Record<string, unknown> | null;
  error: string | null;
}

export interface ChatStatus {
  configured: boolean;
}

export interface BitvavoStatus {
  configured: boolean;
}

export interface BitvavoAssetResult {
  symbol: string;
  coingecko_id: string | null;
  quantity: string;
  average_cost_basis: string | null;
  cost_basis_incomplete: boolean;
  current_value_eur: string | null;
  replaced_entry_labels: string[];
  note: string | null;
  error: string | null;
}

export interface BitvavoSyncResult {
  configured: boolean;
  assets: BitvavoAssetResult[];
  error: string | null;
}
