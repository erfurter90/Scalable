// Maps common CoinGecko coin ids (the free-text slug typed into the entry form, e.g.
// "solana") to their usual ticker symbol (e.g. "SOL") for display next to a quantity. Not
// exhaustive — CoinGecko lists tens of thousands of coins — so this only covers popular ones;
// anything else falls back to showing the id itself, which is still identifiable, just not in
// ticker form. Never guesses a symbol that isn't in this list.
const COIN_TICKERS: Record<string, string> = {
  bitcoin: "BTC",
  ethereum: "ETH",
  solana: "SOL",
  cardano: "ADA",
  ripple: "XRP",
  dogecoin: "DOGE",
  polkadot: "DOT",
  litecoin: "LTC",
  chainlink: "LINK",
  binancecoin: "BNB",
  tron: "TRX",
  "matic-network": "MATIC",
  "avalanche-2": "AVAX",
  stellar: "XLM",
  cosmos: "ATOM",
  monero: "XMR",
  uniswap: "UNI",
  near: "NEAR",
  aptos: "APT",
  arbitrum: "ARB",
  optimism: "OP",
  "shiba-inu": "SHIB",
  pepe: "PEPE",
  sui: "SUI",
  toncoin: "TON",
};

export function coinTicker(coinId: string): string {
  return COIN_TICKERS[coinId] ?? coinId.toUpperCase();
}
