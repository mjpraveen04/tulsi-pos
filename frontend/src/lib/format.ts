import type { Money, UserRole } from "../types";

/** ₹ with en-IN grouping and 2 dp — the currency rule in README Section 7. */
const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Display only: `Money` is a decimal string, so parse it here and nowhere else. */
export function money(value: Money | number | null | undefined): string {
  const amount = Number(value ?? 0);
  return rupees.format(Number.isFinite(amount) ? amount : 0);
}

export function timeOfDay(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function initials(name = ""): string {
  return name
    .split(" ")
    .filter(Boolean)
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function roleLabel(role: UserRole | undefined): string {
  return role === "MANAGER" ? "Manager" : "Cashier";
}
