/**
 * The API contract in TypeScript — one type per Pydantic schema in
 * `backend/app/schemas/`. Anything the API returns is described here so a
 * field rename on the server shows up as a compile error in the UI rather
 * than as `undefined` on a receipt.
 */

export type UserRole = "MANAGER" | "CASHIER";
export type StockMoveReason = "OPENING" | "RECEIVE" | "REMOVE" | "SALE";
export type PaymentMethod = "CASH" | "UPI";

/**
 * Money crosses the wire as a decimal string, never a float (TR-04): the API
 * serialises Python `Decimal`, and parsing it into a JS number is only ever
 * safe for display. Never do arithmetic on a `Money` without `Number(...)`.
 */
export type Money = string;

/** ISO-8601 timestamp / `YYYY-MM-DD` date, as serialised by FastAPI. */
export type IsoDateTime = string;
export type IsoDate = string;

// ---- users -----------------------------------------------------------------

export interface UserPublic {
  id: number;
  name: string;
  role: UserRole;
}

export interface UserDetail extends UserPublic {
  is_active: boolean;
  created_at: IsoDateTime;
}

export interface LoginRequest {
  user_id: number;
  /** Exactly four digits — the server rejects anything else (FR-07). */
  pin: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface UserCreate {
  name: string;
  role: UserRole;
  pin: string;
}

export interface UserUpdate {
  name?: string;
  role?: UserRole;
  pin?: string;
}

// ---- products & stock ------------------------------------------------------

export interface Product {
  id: number;
  name: string;
  category: string;
  price: Money;
  stock: number;
  reorder_level: number;
  photo_url: string | null;
  is_archived: boolean;
  /** Server-computed (FR-17) — the UI never re-derives these thresholds. */
  is_low_stock: boolean;
  is_sold_out: boolean;
}

export interface ProductCreate {
  name: string;
  category: string;
  price: Money;
  opening_stock: number;
  reorder_level: number;
  photo_url?: string | null;
}

/** All fields optional; stock is never edited here, only via the ledger (NFR-06). */
export interface ProductUpdate {
  name?: string;
  category?: string;
  price?: Money;
  reorder_level?: number;
  photo_url?: string | null;
}

export interface MenuCategory {
  category: string;
  products: Product[];
}

export interface MenuOut {
  categories: MenuCategory[];
  products: Product[];
}

export interface StockAdjustRequest {
  /** Always a positive magnitude; the sign comes from `reason` (FR-15). */
  delta: number;
  reason: StockMoveReason;
}

export interface StockMove {
  id: number;
  product_id: number;
  product_name: string;
  delta: number;
  reason: StockMoveReason;
  bill_id: number | null;
  bill_no: number | null;
  user_id: number;
  user_name: string;
  created_at: IsoDateTime;
}

// ---- billing ---------------------------------------------------------------

export interface BillLineIn {
  product_id: number;
  qty: number;
}

/** Cash carries the tendered amount; UPI must not (see `PaymentIn` on the API). */
export type PaymentIn = { method: "CASH"; tendered: Money } | { method: "UPI" };

export interface BillCreate {
  lines: BillLineIn[];
  payment: PaymentIn;
}

export interface BillLine {
  product_id: number;
  name: string;
  qty: number;
  /** Price at the time of sale — a later price edit never rewrites it (FR-25). */
  unit_price: Money;
  line_total: Money;
}

export interface Receipt {
  bill_no: number;
  created_at: IsoDateTime;
  cashier_id: number;
  cashier_name: string;
  lines: BillLine[];
  subtotal: Money;
  gst: Money;
  total: Money;
  method: PaymentMethod;
  tendered: Money | null;
  change_due: Money | null;
  item_count: number;
}

export interface BillSummary {
  bill_no: number;
  created_at: IsoDateTime;
  cashier_name: string;
  item_count: number;
  summary: string;
  total: Money;
  method: PaymentMethod;
}

export interface DailyTotal {
  date: IsoDate;
  total: Money;
  bill_count: number;
  item_count: number;
}

export interface UpiQr {
  upi_id: string;
  payee_name: string;
  intent_url: string;
  qr_data_uri: string;
}

// ---- register cart (client-side only) --------------------------------------

export interface CartLine {
  productId: number;
  qty: number;
}

/** A cart line resolved against the live menu, so stock changes show up at once. */
export interface ResolvedCartLine extends CartLine {
  product: Product;
}
