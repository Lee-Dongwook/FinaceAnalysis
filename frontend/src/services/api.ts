export interface AnalysisRequest {
  investment_amount_krw: number;
  investment_period_months: number;
  quantitative_analysis_period_months: number;
  risk_profile: "conservative" | "moderate" | "aggressive";
  max_loss_percent: number;
  preferred_asset_types?: Array<"equity" | "bond" | "dividend">;
  theme_industry_keywords?: string[];
  cash_ratio_percent?: number;
}

export interface AnalysisResponse {
  request_id: string;
  status: "completed" | "partial" | "failed";
  analysis: {
    received_conditions: AnalysisRequest;
    message: string;
  } | null;
  data_context?: { source: string; as_of_date: string | null; data_origin: "database" | "krx"; cache_status: "current" | "refreshed" };
  candidate_filtering?: { collected_count: number; eligible_count: number; excluded_count: number };
  news_collection?: { status: "available" | "no_news" | "unavailable" | "not_requested"; selected_etf_count: number; stored_article_count?: number | null; message: string };
  sentiment_analysis?: {
    status: "available" | "insufficient_evidence" | "unavailable" | "not_requested";
    results: Array<{
      ticker: string; article_count: number; status: "available" | "excluded" | "unavailable";
      exclusion_reason: string | null; sentiment_score: number | null; sentiment_rationale: string | null;
      core_issues: string[]; risk_factors: string[]; keywords: string[];
    }>;
  };
  warnings: string[];
  errors: Array<{ code: string; message: string }>;
  quantitative_analysis?: {
    price_basis: string;
    requested_period_months: number;
    requested_start_date: string;
    common_end_date: string;
    weekly_sampling_policy: { weekday: number | null; holiday_rule: string; minimum_observations: number; status: string };
    risk_free_rate: { source: string; annual_rate_percent: number | null; weekly_conversion: string; status: string };
    score_weights: Record<string, Record<"conservative" | "moderate" | "aggressive", number>>;
    candidates: Array<{
      ticker: string; name: string; total_return_percent: number | null;
      annualized_volatility_percent: number | null; max_drawdown_percent: number | null;
      sharpe_ratio: number | null; average_trade_value_krw: number | null;
      statuses: string[]; score: { status: string; value: number; rank: number; normalized_scores: Record<string, number> } | null;
    }>;
  };
  portfolio?: {
    status: "available" | "insufficient_candidates" | "insufficient_sentiment";
    investable_amount_krw: number; cash_amount_krw: number; unallocated_amount_krw: number;
    holding_period_months: number; summary: string; warnings: string[];
    holdings: Array<{ ticker: string; name: string; weight_percent: number; target_amount_krw: number; purchase_units: number; purchase_amount_krw: number; holding_period_months: number; quantitative_score: number; sentiment_score: number | null; recommendation_rationale: string[]; risk_factors: string[] }>;
  };
  disclaimer: string;
}

export interface EtfHoldingsResponse {
  status: "available" | "unsupported_provider" | "source_unavailable";
  ticker: string;
  etf_name: string;
  as_of_date: string | null;
  collected_at: string | null;
  source: string;
  source_url: string | null;
  data_origin: "database" | "official_site" | "none";
  cache_status: "current" | "refreshed" | "unavailable";
  source_record_count: number;
  excluded_record_count: number;
  constituents: Array<{
    constituent_code: string; constituent_name: string; weight_percent: number;
    quantity: number | null; evaluation_amount_krw: number | null;
    current_price_krw: number | null; price_change_krw: number | null;
  }>;
  message: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function readJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) throw new Error(body?.detail || fallbackMessage);
  return body as T;
}

export async function requestAnalysis(request: AnalysisRequest): Promise<AnalysisResponse> {
  const response = await fetch(`${apiBaseUrl}/api/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return readJsonResponse<AnalysisResponse>(response, "Analysis request failed.");
}

export async function requestEtfHoldings(ticker: string): Promise<EtfHoldingsResponse> {
  const response = await fetch(`${apiBaseUrl}/api/etfs/${encodeURIComponent(ticker)}/holdings`);
  if (!response.ok) throw new Error("ETF 구성 종목을 불러오지 못했습니다.");
  return (await response.json()) as EtfHoldingsResponse;
}
