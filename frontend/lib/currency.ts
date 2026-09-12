/**
 * Multi-Currency conversion and formatting utility.
 * Allows WhichCloud users to view cloud bills and estimates in their preferred currency.
 */

export type CurrencyCode = "USD" | "EUR" | "GBP" | "INR" | "JPY";

export interface CurrencyConfig {
  code: CurrencyCode;
  symbol: string;
  rate: number; // Against USD
  label: string;
}

export const CURRENCIES: Record<CurrencyCode, CurrencyConfig> = {
  USD: { code: "USD", symbol: "$", rate: 1.0, label: "USD ($) - US Dollar" },
  EUR: { code: "EUR", symbol: "€", rate: 0.92, label: "EUR (€) - Euro" },
  GBP: { code: "GBP", symbol: "£", rate: 0.79, label: "GBP (£) - British Pound" },
  INR: { code: "INR", symbol: "₹", rate: 86.5, label: "INR (₹) - Indian Rupee" },
  JPY: { code: "JPY", symbol: "¥", rate: 154.0, label: "JPY (¥) - Japanese Yen" },
};

/**
 * Format a USD cost value into the selected currency.
 */
export function formatCurrency(
  valueUsd: number,
  currency: CurrencyCode = "USD",
  decimals: number = 2
): string {
  const config = CURRENCIES[currency] || CURRENCIES.USD;
  const converted = valueUsd * config.rate;

  if (currency === "JPY") {
    // JPY does not typically use decimal places
    return `${config.symbol}${Math.round(converted).toLocaleString("en-US")}`;
  }

  return `${config.symbol}${converted.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
