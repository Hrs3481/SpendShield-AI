export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface SafeToSpend {
  safe_to_spend_today: number;
  remaining_budget: number;
  days_remaining: number;
  recommended_daily_discretionary: number;
  overspend_risk: RiskLevel;
  financial_health_score: number;
  explanation_factors: string[];
  /** False when no budget exists this month — every figure above is then zero
   *  for lack of input, which is a different thing from having no money. */
  has_budget: boolean;
}

export interface PurchaseEvaluation {
  affordability_score: number;
  budget_impact_pct: number;
  recommendation: "BUY_NOW" | "WAIT" | "SKIP";
  reason: string;
  intervention_level: number;
  impulse_score: number;
  impulse_label: RiskLevel | "LOW" | "MEDIUM" | "HIGH";
  impulse_reasons: string[];
  intervention_triggers: string[];
}

export interface Transaction {
  id: string;
  amount: number;
  merchant: string | null;
  category: string;
  subcategory: string | null;
  transaction_date: string;
  payment_method: string | null;
  is_essential: boolean;
  is_recurring: boolean;
  is_income: boolean;
  impulse_score: number;
  source: string;
  notes: string | null;
}

export interface TransactionCreate {
  amount: number;
  merchant?: string;
  category: string;
  transaction_date: string;
  payment_method?: string;
  is_essential?: boolean;
  is_recurring?: boolean;
  is_income?: boolean;
  notes?: string;
}

export interface BudgetRule {
  category: string;
  allocated_amount: number;
}

export interface Budget {
  id: string;
  month: number;
  year: number;
  total_income: number;
  savings_target: number;
  rules: BudgetRule[];
}

export interface BudgetUpsert {
  total_income: number;
  savings_target?: number;
  rules?: BudgetRule[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  is_demo: boolean;
}

export interface Forecast {
  predicted_total_month_spend: number;
  predicted_remaining_spend: number;
  target_budget: number;
  projected_overspend: number;
  risk: RiskLevel;
  method: string;
}

export interface Velocity {
  current_velocity: number;
  required_velocity: number;
  deviation_pct: number;
  label: "ON_PACE" | "AHEAD" | "BEHIND";
}

export interface CategorySpend {
  category: string;
  total: number;
  transaction_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  tool_calls_made: string[];
}
