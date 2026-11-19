// tasks/prd-random-jeju-merge.md US-017: the paywall is off unless NEXT_PUBLIC_PAYWALL_ENABLED=true (and the
// backend's PAYWALL_ENABLED=true). Off: no tier badge, no lock card, and /course/{id}/purchase goes back to the course.
export const PAYWALL_ENABLED = process.env.NEXT_PUBLIC_PAYWALL_ENABLED === "true";

// 6.5 / Q-19 — the price is not decided yet. Change it here only.
export const PREMIUM_PRICE_AMOUNT = "₩4,900";
/** English label, kept for callers that need the whole phrase. The purchase screen shows
 *  PREMIUM_PRICE_AMOUNT with a unit in the traveler's language. */
export const PREMIUM_PRICE_LABEL = `${PREMIUM_PRICE_AMOUNT} per day plan`;
