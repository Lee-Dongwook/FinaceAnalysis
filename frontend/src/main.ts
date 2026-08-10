import "./styles/main.css";
import { requestAnalysis, requestEtfHoldings, type AnalysisResponse, type EtfHoldingsResponse } from "./services/api";

type RiskProfile = "conservative" | "moderate" | "aggressive";
type FieldName = "amount" | "period" | "risk" | "loss" | "cash" | "theme";
type ValidationResult = { valid: boolean; errors: Partial<Record<FieldName, string>> };
type QuantSortKey = "score" | "return" | "volatility" | "mdd" | "sharpe" | "tradeValue";

const app = document.querySelector<HTMLElement>("#app");
let quantSort: { key: QuantSortKey; descending: boolean } = { key: "score", descending: true };
let quantitativeAnalysisPeriodMonths = 12;

function parseInvestmentAmount(value: string): number {
  return Number(value.replaceAll(",", ""));
}

function formatInvestmentAmount(input: HTMLInputElement): void {
  const digits = input.value.replaceAll(/[^\d]/g, "");
  input.value = digits ? Number(digits).toLocaleString("ko-KR") : "";
}

function parseThemeIndustryKeywords(value: string): string[] {
  return value.split(/[,;\n]/).map((keyword) => keyword.trim()).filter(Boolean);
}

function validate(form: HTMLFormElement): ValidationResult {
  const values = new FormData(form);
  const errors: Partial<Record<FieldName, string>> = {};
  const amountText = String(values.get("amount") ?? "").trim();
  const periodText = String(values.get("period") ?? "").trim();
  const lossText = String(values.get("loss") ?? "").trim();
  const cashText = String(values.get("cash") ?? "").trim();
  const themeKeywords = parseThemeIndustryKeywords(String(values.get("theme") ?? ""));
  const amount = parseInvestmentAmount(amountText);
  const period = Number(periodText);
  const loss = Number(lossText);
  const cash = Number(cashText);

  if (!amountText || !Number.isInteger(amount) || amount < 1_000_000 || amount > 1_000_000_000) errors.amount = "투자금은 100만 원 이상 10억 원 이하의 정수로 입력하세요.";
  if (!periodText || !Number.isInteger(period) || period < 1 || period > 60) errors.period = "투자 기간은 1개월 이상 60개월 이하로 입력하세요.";
  if (!values.get("risk")) errors.risk = "위험 성향을 선택하세요.";
  if (!lossText || Number.isNaN(loss) || loss < 0 || loss > 100) errors.loss = "허용 손실은 0% 이상 100% 이하로 입력하세요.";
  if (cashText && (Number.isNaN(cash) || cash < 0 || cash > 100)) errors.cash = "현금성 비중은 0% 이상 100% 이하로 입력하거나 비워 두세요.";
  if (themeKeywords.length > 5 || themeKeywords.some((keyword) => keyword.length > 50)) {
    errors.theme = "테마·산업군 키워드는 최대 5개, 키워드당 50자까지 입력할 수 있습니다.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

function renderErrors(form: HTMLFormElement, result: ValidationResult): void {
  (Object.keys({ amount: 1, period: 1, risk: 1, loss: 1, cash: 1, theme: 1 }) as FieldName[]).forEach((name) => {
    const field = form.querySelector<HTMLElement>(`[data-field="${name}"]`);
    const error = form.querySelector<HTMLElement>(`[data-error="${name}"]`);
    field?.classList.toggle("is-invalid", Boolean(result.errors[name]));
    if (error) error.textContent = result.errors[name] ?? "";
  });
  const summary = form.querySelector<HTMLElement>("#error-summary");
  summary?.classList.toggle("visible", !result.valid);
  if (summary && !result.valid) summary.textContent = "입력값을 확인한 뒤 다시 시도하세요.";
  const button = form.querySelector<HTMLButtonElement>("button[type=submit]");
  if (button) button.disabled = !result.valid;
}

const formatNumber = (value: number | null, suffix = "") => value === null ? "산출 불가" : `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${suffix}`;
const escapeHtml = (value: string) => value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character] ?? character));
const metricWithScore = (value: number | null, suffix: string, score: number | undefined) => `${formatNumber(value, suffix)}<small>${score === undefined ? "점수 보류" : `${formatNumber(score)}점`}</small>`;
const statusMessage: Record<string, string> = {
  insufficient_history: "요청 기간을 충족하는 가격 이력이 부족합니다.",
  insufficient_weekly_observations: "연환산 변동성·샤프지수에 필요한 주간 관측값 30개가 부족합니다.",
  weekly_sampling_policy_pending: "주간 표본일 정책이 설정되지 않아 변동성·샤프지수를 계산하지 않았습니다.",
  kofr_rate_pending: "KOFR 무위험수익률이 설정되지 않아 샤프지수를 계산하지 않았습니다.",
  zero_denominator: "주간 수익률의 변동성이 0이라 샤프지수를 계산할 수 없습니다.",
  available_history_shortened: "요청 기간보다 짧은 현재 보관 이력으로 계산했습니다.",
};

function renderMethodology(
  data: NonNullable<AnalysisResponse["quantitative_analysis"]>,
  riskProfile: RiskProfile | undefined,
): string {
  const labels: Record<string, string> = {
    return: "기간 수익률", volatility: "연환산 변동성", mdd: "MDD",
    sharpe: "샤프지수", average_trade_value_krw: "평균 거래대금",
  };
  const weekday = data.weekly_sampling_policy.weekday === null
    ? "미설정" : ["월", "화", "수", "목", "금", "토", "일"][data.weekly_sampling_policy.weekday] ?? "미설정";
  const weightItems = Object.entries(data.score_weights).map(([key, weights]) =>
    `<li><span>${labels[key] ?? key}</span><b>${riskProfile ? `${weights[riskProfile]}%` : "—"}</b></li>`,
  ).join("");
  return `<details class="methodology-toggle"><summary><span><i class="status-dot"></i>calculation methodology</span><b>계산 기준 · 가중치 <em>⌄</em></b></summary><div class="methodology-content"><div class="methodology-block"><h3>계산 기준</h3><dl><div><dt>분석 기간</dt><dd>${data.requested_start_date} ~ ${data.common_end_date} (${data.requested_period_months}개월)</dd></div><div><dt>가격 기준</dt><dd>${data.price_basis}</dd></div><div><dt>주간 표본</dt><dd>${weekday}요일 기준 · ${data.weekly_sampling_policy.holiday_rule} · 최소 ${data.weekly_sampling_policy.minimum_observations}개</dd></div><div><dt>무위험수익률</dt><dd>${data.risk_free_rate.source} ${data.risk_free_rate.annual_rate_percent ?? "미설정"}% · ${data.risk_free_rate.weekly_conversion}</dd></div><div><dt>결측 처리</dt><dd>0 이하 가격·중복 관측치는 제외하고, 분석 기간보다 이력이 짧으면 보유 이력으로 계산합니다.</dd></div></dl></div><div class="methodology-block"><h3>현재 적합점수 가중치</h3><p>${riskProfile ? `${({ conservative: "안정형", moderate: "중립형", aggressive: "공격형" }[riskProfile])} 기준 · 최소-최대 정규화(0~100점)` : "위험 성향 정보 없음"}</p><ul class="weight-list">${weightItems}</ul><small>수익률·샤프지수·평균 거래대금은 높을수록, 변동성·MDD는 낮을수록 높은 점수를 받습니다. 모든 값이 같으면 50점을 적용합니다.</small></div></div></details>`;
}

function renderQuantitativeResult(response: AnalysisResponse): void {
  const section = document.querySelector<HTMLElement>("#quantitative-result");
  const target = document.querySelector<HTMLElement>("#quantitative-candidates");
  const meta = document.querySelector<HTMLElement>("#quantitative-meta");
  const data = response.quantitative_analysis;
  if (!section || !target || !meta || !data) { section?.classList.remove("visible"); return; }
  section.classList.add("visible");
  const methodology = renderMethodology(data, response.analysis?.received_conditions.risk_profile);
  meta.textContent = `${data.requested_start_date} ~ ${data.common_end_date} · ${data.requested_period_months}개월 · KOFR 가정 ${data.risk_free_rate.annual_rate_percent}%`;
  const valueForSort = (item: typeof data.candidates[number], key: QuantSortKey): number | null => ({
    score: item.score?.value ?? null, return: item.total_return_percent,
    volatility: item.annualized_volatility_percent, mdd: item.max_drawdown_percent,
    sharpe: item.sharpe_ratio, tradeValue: item.average_trade_value_krw,
  }[key]);
  const candidates = [...data.candidates].sort((left, right) => {
    const leftValue = valueForSort(left, quantSort.key), rightValue = valueForSort(right, quantSort.key);
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    if (leftValue === rightValue) return left.ticker.localeCompare(right.ticker);
    return quantSort.descending ? rightValue - leftValue : leftValue - rightValue;
  });
  const sortHeader = (label: string, key: QuantSortKey) => `<th><button class="sort-button ${quantSort.key === key ? "active" : ""}" data-sort="${key}">${label}<span>${quantSort.key === key ? (quantSort.descending ? "↓" : "↑") : "↕"}</span></button></th>`;
  const rows = candidates.map((item, index) => {
    const reason = item.statuses.length ? item.statuses.map((status) => statusMessage[status] ?? status).join(" ") : "모든 정량지표가 계산되었습니다.";
    const scores = item.score?.normalized_scores;
    return `<tr><td class="number-cell">${index + 1}</td><td><b>${item.name}</b><span>${item.ticker}</span></td><td>${item.score ? `${formatNumber(item.score.value)}점<br /><small>${item.score.rank}위</small>` : "산출 보류"}</td><td>${metricWithScore(item.total_return_percent, "%", scores?.return)}</td><td>${metricWithScore(item.annualized_volatility_percent, "%", scores?.volatility)}</td><td>${metricWithScore(item.max_drawdown_percent, "%", scores?.mdd)}</td><td>${metricWithScore(item.sharpe_ratio, "", scores?.sharpe)}</td><td>${metricWithScore(item.average_trade_value_krw, "원", scores?.liquidity)}</td><td class="reason-cell">${reason}</td></tr>`;
  }).join("");
  target.innerHTML = `${methodology}${rows ? `<div class="quant-table-wrap"><table class="quant-table"><thead><tr><th>번호</th><th>ETF</th>${sortHeader("적합점수", "score")}${sortHeader("수익률", "return")}${sortHeader("변동성", "volatility")}${sortHeader("MDD", "mdd")}${sortHeader("샤프", "sharpe")}${sortHeader("평균 거래대금", "tradeValue")}<th>산출 상태·사유</th></tr></thead><tbody>${rows}</tbody></table></div>` : "<p class=\"empty-result\">정량 분석 가능한 1차 후보가 없습니다.</p>"}`;
  target.querySelectorAll<HTMLButtonElement>("[data-sort]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.sort as QuantSortKey;
    quantSort = { key, descending: quantSort.key === key ? !quantSort.descending : true };
    renderQuantitativeResult(response);
  }));
}

function renderAnalysisProgress(response: AnalysisResponse): void {
  const section = document.querySelector<HTMLElement>("#analysis-progress");
  const target = document.querySelector<HTMLElement>("#analysis-progress-content");
  if (!section || !target) return;
  const data = response.data_context;
  const candidates = response.candidate_filtering;
  const quantitative = response.quantitative_analysis;
  const news = response.news_collection;
  const sentiment = response.sentiment_analysis;
  const portfolio = response.portfolio;
  const state = (complete: boolean, detail: string, partial = false) => ({
    className: complete ? "complete" : partial ? "partial" : "pending",
    label: complete ? "완료" : partial ? "부분 완료" : "보류",
    detail,
  });
  const stages = [
    ["입력 조건 확인", state(Boolean(response.analysis), response.analysis ? "입력값 검증 완료" : "입력값 확인 필요")],
    ["ETF 데이터 확인", state(Boolean(data), data ? `${data.as_of_date ?? "기준일 미확인"} · ${data.data_origin === "database" ? "DB 데이터" : "KRX 수집"}` : "데이터 확인 보류")],
    ["1차 후보 필터링", state(Boolean(candidates), candidates ? `${candidates.eligible_count}개 후보 / 전체 ${candidates.collected_count}개` : "후보 필터링 보류")],
    ["정량 분석", state(Boolean(quantitative), quantitative ? `${quantitative.candidates.length}개 후보 지표 계산` : "정량 분석 보류")],
    ["뉴스·감성 분석", state(sentiment?.status === "available", sentiment?.status === "available" ? `${sentiment.results.length}개 ETF 감성 결과` : news?.status === "available" ? `뉴스 ${news.selected_etf_count}개 ETF 수집, 감성 분석 보류` : "뉴스·감성 근거 부족", Boolean(news && news.status !== "not_requested"))],
    ["결과 종합", state(portfolio?.status === "available", portfolio?.status === "available" ? `${portfolio.holdings.length}개 ETF 포트폴리오 구성` : portfolio?.summary ?? "결과 종합 보류", Boolean(portfolio))],
  ] as const;
  section.classList.add("visible");
  target.innerHTML = `<div class="progress-grid">${stages.map(([title, item], index) => `<article class="progress-step ${item.className}"><span class="progress-number">${String(index + 1).padStart(2, "0")}</span><div><h3>${title}</h3><strong>${item.label}</strong><p>${escapeHtml(item.detail)}</p></div></article>`).join("")}</div>`;
}

function renderPortfolioRadarChart(
  response: AnalysisResponse,
  portfolio: NonNullable<AnalysisResponse["portfolio"]>,
): string {
  const metrics = [
    { key: "return", label: "수익률" },
    { key: "volatility", label: "변동성" },
    { key: "mdd", label: "MDD" },
    { key: "sharpe", label: "샤프" },
    { key: "liquidity", label: "거래대금" },
  ] as const;
  const colors = ["#0071e3", "#34c759", "#af52de", "#ff9f0a", "#ff375f"];
  const quantitativeByTicker = new Map(
    (response.quantitative_analysis?.candidates ?? []).map((item) => [item.ticker, item]),
  );
  const series = portfolio.holdings.slice(0, colors.length).flatMap((holding, index) => {
    const normalizedScores = quantitativeByTicker.get(holding.ticker)?.score?.normalized_scores;
    if (!normalizedScores) return [];
    return [{ name: holding.name, ticker: holding.ticker, color: colors[index], normalizedScores }];
  });
  if (!series.length) {
    return `<section class="portfolio-radar"><div class="portfolio-radar-heading"><div><span class="status-label"><i class="status-dot"></i>quantitative comparison</span><h3>추천 ETF 정량 지표 비교</h3></div></div><p class="empty-result">레이더 차트에 사용할 정량 점수가 없습니다.</p></section>`;
  }

  const center = 180;
  const radius = 116;
  const point = (value: number, index: number, distance = radius) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / metrics.length;
    const scaledDistance = distance * value / 100;
    return `${(center + Math.cos(angle) * scaledDistance).toFixed(1)},${(center + Math.sin(angle) * scaledDistance).toFixed(1)}`;
  };
  const rings = [25, 50, 75, 100].map((value) =>
    `<polygon class="radar-ring" points="${metrics.map((_, index) => point(value, index)).join(" ")}" />`,
  ).join("");
  const axes = metrics.map((metric, index) => {
    const labelPoint = point(100, index, radius + 25).split(",");
    return `<line class="radar-axis" x1="${center}" y1="${center}" x2="${point(100, index)}" /><text class="radar-label" x="${labelPoint[0]}" y="${Number(labelPoint[1]) + 4}" text-anchor="middle">${metric.label}</text>`;
  }).join("");
  const datasets = series.map((item) => {
    const points = metrics.map((metric, index) => {
      const value = item.normalizedScores[metric.key];
      return point(typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0, index);
    }).join(" ");
    return `<polygon class="radar-dataset" points="${points}" fill="${item.color}" stroke="${item.color}" />`;
  }).join("");
  const legend = series.map((item) =>
    `<li><i style="background:${item.color}"></i><span>${escapeHtml(item.name)}</span><small>${escapeHtml(item.ticker)}</small></li>`,
  ).join("");
  return `<section class="portfolio-radar"><div class="portfolio-radar-heading"><div><span class="status-label"><i class="status-dot"></i>quantitative comparison</span><h3>추천 ETF 정량 지표 비교</h3></div><p>각 축은 후보군 내 0~100 정규화 점수입니다. 변동성과 MDD는 낮을수록 높은 점수로 환산됩니다.</p></div><div class="portfolio-radar-content"><svg class="radar-chart" viewBox="0 0 360 360" role="img" aria-label="추천 ETF 정량 지표 레이더 차트">${rings}${axes}${datasets}</svg><ul class="radar-legend">${legend}</ul></div></section>`;
}

function renderPortfolio(response: AnalysisResponse): void {
  const section = document.querySelector<HTMLElement>("#portfolio-result");
  const target = document.querySelector<HTMLElement>("#portfolio-content");
  const portfolio = response.portfolio;
  if (!section || !target || !portfolio) return;
  section.classList.add("visible");
  if (portfolio.status !== "available") { target.innerHTML = `<p class="empty-result">${portfolio.summary}</p>`; return; }
  const money = (value: number) => `${value.toLocaleString("ko-KR")}원`;
  const quantitativeByTicker = new Map(
    (response.quantitative_analysis?.candidates ?? []).map((item) => [item.ticker, item]),
  );
  const sentimentByTicker = new Map(
    (response.sentiment_analysis?.results ?? []).map((item) => [item.ticker, item]),
  );
  const metric = (value: number | null | undefined, suffix = "") =>
    value === undefined || value === null ? "—" : formatNumber(value, suffix);
  const rows = portfolio.holdings.map((item) => {
    const quantitative = quantitativeByTicker.get(item.ticker);
    return `<tr><td><b>${escapeHtml(item.name)}</b><span>${item.ticker}</span></td><td>${item.weight_percent}%<small>${money(item.target_amount_krw)}</small></td><td>${formatNumber(item.quantitative_score)}점<small>${quantitative?.score?.rank ?? "—"}위</small></td><td>${metric(quantitative?.total_return_percent, "%")}</td><td>${metric(quantitative?.annualized_volatility_percent, "%")}</td><td>${metric(quantitative?.max_drawdown_percent, "%")}</td><td>${metric(quantitative?.sharpe_ratio)}</td><td>${metric(quantitative?.average_trade_value_krw, "원")}</td><td><button type="button" class="holdings-button" data-holdings-ticker="${item.ticker}" data-holdings-name="${escapeHtml(item.name)}">보기</button></td></tr>`;
  }).join("");
  const insightCards = portfolio.holdings.map((item) => {
    const sentiment = sentimentByTicker.get(item.ticker);
    const rationale = item.recommendation_rationale.length
      ? item.recommendation_rationale.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")
      : "<li>제공된 선정 근거가 없습니다.</li>";
    const risks = item.risk_factors.length
      ? item.risk_factors.map((risk) => `<li>${escapeHtml(risk)}</li>`).join("")
      : "<li>확인된 추가 위험요인이 없습니다.</li>";
    const sentimentSummary = sentiment?.status === "available"
      ? `<section class="sentiment"><h4>뉴스·감성 요약</h4><ul class="sentiment-list"><li><span>검증 뉴스</span><b>${sentiment.article_count}건</b></li><li><span>감성 점수</span><b>${sentiment.sentiment_score ?? "—"}점</b></li><li class="sentiment-detail"><span>분석 근거</span><p>${escapeHtml(sentiment.sentiment_rationale ?? "감성 근거가 제공되지 않았습니다.")}</p></li>${sentiment.core_issues.length ? `<li class="sentiment-detail"><span>핵심 이슈</span><p>${escapeHtml(sentiment.core_issues.join(" · "))}</p></li>` : ""}</ul></section>`
      : `<section class="sentiment muted"><h4>뉴스·감성 요약</h4><ul class="sentiment-list"><li>${escapeHtml(sentiment?.exclusion_reason ?? "검증된 뉴스·감성 분석 결과가 없습니다.")}</li></ul></section>`;
    return `<article class="portfolio-insight-card"><header><span class="portfolio-insight-ticker">${item.ticker}</span><h3>${escapeHtml(item.name)}</h3><p>추천 비중 ${item.weight_percent}% · 보유 기간 ${item.holding_period_months}개월</p></header><div class="portfolio-insight-copy"><section><h4>선정 근거</h4><ul>${rationale}</ul></section>${sentimentSummary}<section class="risk"><h4>위험 요인</h4><ul>${risks}</ul></section></div></article>`;
  }).join("");
  target.innerHTML = `<p class="portfolio-summary">${escapeHtml(portfolio.summary)}</p><div class="portfolio-meta">투자 가능 ${money(portfolio.investable_amount_krw)} · 현금 ${money(portfolio.cash_amount_krw)} · 미배정 ${money(portfolio.unallocated_amount_krw)} · 보유 ${portfolio.holding_period_months}개월</div><div class="portfolio-table-heading"><div><span class="status-label"><i class="status-dot"></i>quantitative snapshot</span><h3>추천 ETF 정량 지표 요약</h3></div><p>종가 기준 정량 분석 결과이며, 산출되지 않은 값은 대시(—)로 표시됩니다.</p></div><div class="quant-table-wrap"><table class="quant-table portfolio-quant-table"><thead><tr><th>ETF</th><th>추천 비중</th><th>적합점수</th><th>수익률</th><th>변동성</th><th>MDD</th><th>샤프</th><th>평균 거래대금</th><th>구성 종목</th></tr></thead><tbody>${rows}</tbody></table></div>${renderPortfolioRadarChart(response, portfolio)}<div class="portfolio-insights-heading"><div><span class="status-label"><i class="status-dot"></i>recommendation notes</span><h3>ETF별 선정 근거와 위험 요인</h3></div><p>각 ETF의 설명을 정량 지표 표와 분리해 확인할 수 있습니다.</p></div><div class="portfolio-insights">${insightCards}</div><p class="quant-disclaimer">${portfolio.warnings.map(escapeHtml).join(" ")} 최종 투자 결정은 사용자의 책임입니다.</p>`;
  target.querySelectorAll<HTMLButtonElement>("[data-holdings-ticker]").forEach((button) => button.addEventListener("click", async () => {
    const ticker = button.dataset.holdingsTicker;
    if (!ticker) return;
    button.disabled = true;
    button.textContent = "불러오는 중…";
    renderHoldingsLoading(button.dataset.holdingsName ?? ticker);
    try { renderHoldingsResult(await requestEtfHoldings(ticker)); }
    catch { renderHoldingsError("구성 종목 데이터를 불러오지 못했습니다. Backend 연결과 서버 로그를 확인하세요."); }
    finally { button.disabled = false; button.textContent = "보기"; }
  }));
}

function renderHoldingsLoading(etfName: string): void {
  const section = document.querySelector<HTMLElement>("#holdings-result");
  const target = document.querySelector<HTMLElement>("#holdings-content");
  if (!section || !target) return;
  section.classList.add("visible");
  target.innerHTML = `<p class="empty-result"><b>${escapeHtml(etfName)}</b>의 운용사 공식 구성종목 데이터를 확인하고 있습니다…</p>`;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderHoldingsError(message: string): void {
  const target = document.querySelector<HTMLElement>("#holdings-content");
  if (target) target.innerHTML = `<p class="empty-result">${escapeHtml(message)}</p>`;
}

function renderHoldingsResult(response: EtfHoldingsResponse): void {
  const title = document.querySelector<HTMLElement>("#holdings-title");
  const meta = document.querySelector<HTMLElement>("#holdings-meta");
  const target = document.querySelector<HTMLElement>("#holdings-content");
  if (!title || !meta || !target) return;
  title.textContent = `${response.etf_name} 구성 종목`;
  meta.textContent = response.as_of_date ? `구성 기준일 ${response.as_of_date} · ${response.constituents.length.toLocaleString("ko-KR")}개 종목` : "구성 종목 데이터 상태";
  if (response.status !== "available") {
    target.innerHTML = `<p class="empty-result">${escapeHtml(response.message)}</p>`;
    return;
  }
  const money = (value: number | null) => value === null ? "—" : `${value.toLocaleString("ko-KR")}원`;
  const rows = response.constituents.map((item, index) => `<tr><td>${index + 1}</td><td><b>${escapeHtml(item.constituent_name)}</b><span>${escapeHtml(item.constituent_code)}</span></td><td>${item.weight_percent.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%</td><td>${item.quantity?.toLocaleString("ko-KR") ?? "—"}</td><td>${money(item.current_price_krw)}</td><td>${money(item.evaluation_amount_krw)}</td></tr>`).join("");
  const sourceLink = response.source_url ? `<a href="${escapeHtml(response.source_url)}" target="_blank" rel="noreferrer">공식 원천 열기</a>` : "공식 원천 URL 없음";
  target.innerHTML = `<div class="holdings-summary"><span>${escapeHtml(response.source)}</span><span>${response.cache_status === "refreshed" ? "이번 조회에서 갱신" : "오늘 수집한 DB 데이터"}</span>${sourceLink}</div><div class="quant-table-wrap"><table class="quant-table holdings-table"><thead><tr><th>순위</th><th>구성 종목</th><th>편입 비중</th><th>수량</th><th>현재가</th><th>평가액</th></tr></thead><tbody>${rows}</tbody></table></div><p class="quant-disclaimer">${escapeHtml(response.message)} 원천 ${response.source_record_count}건 중 현금성 자산 또는 비중 누락 ${response.excluded_record_count}건은 표에서 제외했습니다.</p>`;
}

if (app) {
  app.className = "app-shell";
  app.innerHTML = `
    <nav class="nav"><div class="brand"><span class="brand-mark"></span>atlas</div><span class="nav-note">ETF analysis, thoughtfully simplified</span></nav>
    <header class="hero">
      <div><p class="eyebrow">Personal investment workspace</p><h1>당신의 조건에서<br />시작하는 ETF 탐색.</h1><p class="hero-copy">투자 조건을 먼저 정리하면, 이후의 ETF 데이터와 시장 정보를 더 일관된 기준으로 살펴볼 수 있습니다.</p></div>
    </header>
    <main class="workspace">
      <section class="panel form-panel">
        <div class="panel-title"><div><h2>투자 조건</h2><p>필수 정보를 입력하면 분석 요청을 준비합니다.</p></div><span class="required-key"><b>•</b> 필수 입력</span></div>
        <div class="period-picker panel-period-picker" aria-label="정량 분석 기간"><span>정량 분석 기간</span><div role="group" class="period-options"><button type="button" data-quant-period="1">1개월</button><button type="button" data-quant-period="3">3개월</button><button type="button" data-quant-period="6">6개월</button><button type="button" data-quant-period="12" class="active">12개월</button></div></div>
        <form id="analysis-form" novalidate>
          <div class="form-grid">
            <div class="field" data-field="amount"><div class="field-head">투자금 <span class="required">•</span></div><div class="input-wrap has-suffix"><input name="amount" inputmode="numeric" value="10,000,000" aria-describedby="amount-error" /><span class="suffix">원</span></div><small class="field-hint">100만 원 ~ 10억 원 · 천 단위 자동 표시</small><span class="error" id="amount-error" data-error="amount"></span></div>
            <div class="field" data-field="period"><div class="field-head">투자 기간 <span class="required">•</span></div><div class="input-wrap has-suffix"><input name="period" inputmode="numeric" value="12" aria-describedby="period-error" /><span class="suffix">개월</span></div><small class="field-hint">1개월 ~ 60개월</small><span class="error" id="period-error" data-error="period"></span></div>
            <div class="field" data-field="risk"><div class="field-head">위험 성향 <span class="required">•</span></div><select name="risk" aria-describedby="risk-error"><option value="conservative">안정형 · 변동성 최소화</option><option value="moderate" selected>중립형 · 균형 있는 접근</option><option value="aggressive">공격형 · 성장 중심</option></select><span class="error" id="risk-error" data-error="risk"></span></div>
            <div class="field" data-field="loss"><div class="field-head">허용 손실 <span class="required">•</span></div><div class="input-wrap has-suffix"><input name="loss" inputmode="decimal" value="20" aria-describedby="loss-error" /><span class="suffix">%</span></div><small class="field-hint">0% ~ 100%</small><span class="error" id="loss-error" data-error="loss"></span></div>
            <div class="field full"><div class="field-head">선호 자산 <span class="field-hint">선택 · 복수 선택 가능</span></div><div class="choice-grid"><label class="choice"><input type="checkbox" name="asset" value="equity" checked /><span>주식형</span></label><label class="choice"><input type="checkbox" name="asset" value="bond" /><span>채권형</span></label><label class="choice"><input type="checkbox" name="asset" value="dividend" /><span>배당형</span></label></div></div>
            <div class="field full" data-field="cash"><div class="field-head">현금성 비중 <span class="field-hint">선택 · 미입력 시 적용하지 않음</span></div><div class="input-wrap has-suffix"><input name="cash" inputmode="decimal" placeholder="예: 10" aria-describedby="cash-error" /><span class="suffix">%</span></div><span class="error" id="cash-error" data-error="cash"></span></div>
          </div>
            <div class="field full" data-field="theme"><div class="field-head">관심 테마·산업군 <span class="field-hint">선택 · 쉼표로 여러 키워드 입력</span></div><div class="input-wrap"><input name="theme" maxlength="150" placeholder="예: 반도체, 인공지능, 2차전지" aria-describedby="theme-error" /></div><small class="field-hint">입력한 키워드가 ETF명 또는 KRX 기초지수·분류에 포함된 후보만 선별합니다.</small><span class="error" id="theme-error" data-error="theme"></span></div>
          <div id="error-summary" class="summary-error" role="alert"></div>
          <div class="submit-row"><span class="submit-note">조건은 분석 요청에만 사용되며, 현재는 저장되지 않습니다.</span><button class="submit-button" type="submit">분석 요청 준비하기</button></div>
        </form>
        <section class="investment-notice" aria-label="투자 유의사항"><span class="notice-icon" aria-hidden="true">💡</span><p>최종 투자 결정과 책임은 사용자에게 있습니다.</p></section>
      </section>
    </main>
    <section class="quantitative-section" id="portfolio-result"><div class="quant-heading"><div><span class="status-label"><i class="status-dot"></i>recommendation portfolio</span><h2>추천 포트폴리오</h2><p>정량 점수와 검증된 뉴스 근거를 함께 표시합니다.</p></div><span class="api-connection-note">정보 제공</span></div><div id="portfolio-content"></div></section>
    <section class="quantitative-section" id="analysis-progress"><div class="quant-heading"><div><span class="status-label"><i class="status-dot"></i>analysis workflow</span><h2>분석 진행 상태</h2><p>이번 분석 요청에서 확인한 단계별 처리 상태입니다.</p></div><span class="api-connection-note">요청 기준</span></div><div id="analysis-progress-content"></div></section>
    <section class="quantitative-section" id="holdings-result"><div class="quant-heading"><div><span class="status-label"><i class="status-dot"></i>official holdings</span><h2 id="holdings-title">ETF 구성 종목</h2><p id="holdings-meta">포트폴리오의 ETF에서 ‘보기’를 선택하세요.</p></div><span class="api-connection-note">운용사 공식 데이터</span></div><div id="holdings-content"></div></section>
    <section class="quantitative-section" id="quantitative-result"><div class="quant-heading"><div><span class="status-label"><i class="status-dot"></i>first-stage analysis</span><h2>1차 분석 추천 ETF</h2><p id="quantitative-meta"></p></div><span class="api-connection-note">일반 코드 계산</span></div><div id="quantitative-candidates"></div><p class="quant-disclaimer">종가 기준 계산값이며, 조정 종가·주간 표본일·KOFR 설정이 없으면 해당 지표와 적합점수는 보류됩니다.</p></section>
    <section class="panel api-connection-panel">
      <div class="api-connection-heading"><div><span class="status-label"><i class="status-dot"></i>API connection</span><h3>분석 요청 결과</h3><p>유효한 투자 조건을 Backend로 전송하고, KRX ETF 수집 및 1차 후보 결과를 표시합니다.</p></div><span class="api-connection-note">실시간 응답</span></div>
      <output class="result" id="result" aria-live="polite">입력값을 확인해 주세요.</output>
    </section>`;

  const form = app.querySelector<HTMLFormElement>("#analysis-form");
  const output = app.querySelector<HTMLOutputElement>("#result");
  if (form && output) {
    const refreshValidation = () => renderErrors(form, validate(form));
    const amountInput = form.elements.namedItem("amount");
    const periodInput = form.elements.namedItem("period");
    if (amountInput instanceof HTMLInputElement) {
      amountInput.addEventListener("input", () => formatInvestmentAmount(amountInput));
    }
    app.querySelectorAll<HTMLButtonElement>("[data-quant-period]").forEach((button) => button.addEventListener("click", () => {
      quantitativeAnalysisPeriodMonths = Number(button.dataset.quantPeriod);
      app.querySelectorAll<HTMLButtonElement>("[data-quant-period]").forEach((option) => option.classList.toggle("active", option === button));
    }));
    form.addEventListener("input", refreshValidation);
    form.addEventListener("change", refreshValidation);
    refreshValidation();
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const checked = validate(form);
      renderErrors(form, checked);
      if (!checked.valid) { form.querySelector<HTMLElement>(".is-invalid input, .is-invalid select")?.focus(); return; }
      const values = new FormData(form);
      const cashText = String(values.get("cash") ?? "").trim();
      const themeKeywords = parseThemeIndustryKeywords(String(values.get("theme") ?? ""));
      output.textContent = "분석 API에 안전하게 연결하고 있습니다…";
      try {
        const response = await requestAnalysis({
          investment_amount_krw: parseInvestmentAmount(String(values.get("amount"))), investment_period_months: Number(values.get("period")), quantitative_analysis_period_months: quantitativeAnalysisPeriodMonths,
          risk_profile: values.get("risk") as RiskProfile, max_loss_percent: Number(values.get("loss")),
          preferred_asset_types: values.getAll("asset") as Array<"equity" | "bond" | "dividend">,
          ...(themeKeywords.length ? { theme_industry_keywords: themeKeywords } : {}),
          ...(cashText ? { cash_ratio_percent: Number(cashText) } : {}),
        });
        renderQuantitativeResult(response);
        renderAnalysisProgress(response);
        renderPortfolio(response);
        output.textContent = JSON.stringify(response, null, 2);
      } catch { output.textContent = "Backend 서버에 연결할 수 없습니다. 서버 실행 상태를 확인하세요."; }
    });
  }
}
