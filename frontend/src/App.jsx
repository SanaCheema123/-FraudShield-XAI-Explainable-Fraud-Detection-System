import { useState, useEffect, useRef, useCallback } from "react";

// ──────────────────────────────────────────────────────────────
// STYLES (injected into <head>)
// ──────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;700;800&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #080c10;
    --surface: #0d1420;
    --surface2: #111b2a;
    --border: #1a2d45;
    --cyan: #00e5ff;
    --cyan-dim: rgba(0,229,255,0.12);
    --green: #00ff88;
    --amber: #ffb800;
    --red: #ff3d5a;
    --critical: #ff0066;
    --text: #c8daf0;
    --text-dim: #4a6580;
    --mono: 'Space Mono', monospace;
    --sans: 'Syne', sans-serif;
  }

  body { background: var(--bg); color: var(--text); font-family: var(--sans); }

  /* Grid noise overlay */
  body::before {
    content: '';
    position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image:
      linear-gradient(rgba(0,229,255,0.015) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,229,255,0.015) 1px, transparent 1px);
    background-size: 40px 40px;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  @keyframes pulse-border {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0,229,255,0.4); }
    50%       { box-shadow: 0 0 0 6px rgba(0,229,255,0); }
  }
  @keyframes scanline {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100vh); }
  }
  @keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position: 200% center; }
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes alertPulse {
    0%,100% { border-color: var(--critical); }
    50%     { border-color: transparent; }
  }
  @keyframes barFill {
    from { width: 0; }
  }
  @keyframes numberCount {
    from { opacity: 0; transform: scale(0.8); }
    to   { opacity: 1; transform: scale(1); }
  }

  .fade-up { animation: fadeSlideUp 0.35s ease both; }

  .risk-low      { color: var(--green); }
  .risk-medium   { color: var(--amber); }
  .risk-high     { color: var(--red); }
  .risk-critical { color: var(--critical); }
`;

function injectCSS(css) {
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  return () => document.head.removeChild(style);
}

// ──────────────────────────────────────────────────────────────
// CONSTANTS & HELPERS
// ──────────────────────────────────────────────────────────────
const RISK_COLORS = {
  low: "#00ff88",
  medium: "#ffb800",
  high: "#ff3d5a",
  critical: "#ff0066",
  pending: "#4a6580",
};

const RISK_LABELS = {
  low: "LOW RISK",
  medium: "MEDIUM RISK",
  high: "HIGH RISK",
  critical: "CRITICAL",
  pending: "PENDING",
};

const MERCHANT_CATEGORIES = [
  "Retail", "Food & Dining", "Travel", "Entertainment",
  "Healthcare", "Education", "Utilities", "Gas", "Jewelry", "Crypto Exchange",
];

function riskColor(level) {
  return RISK_COLORS[level] || "#4a6580";
}

function formatMoney(n) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

function formatPercent(n) {
  return (n * 100).toFixed(1) + "%";
}

// ──────────────────────────────────────────────────────────────
// MOCK API (no backend needed for preview)
// ──────────────────────────────────────────────────────────────
function mockAnalyze(txnData) {
  return new Promise(resolve => setTimeout(() => {
    const amount = txnData.amount || 100;
    const isInt = txnData.is_international;
    const isOnline = txnData.is_online;
    const hour = txnData.hour_of_day;
    const velocity = txnData.transaction_velocity_1h;

    let score = 0.05;
    if (amount > 5000) score += 0.35;
    else if (amount > 1000) score += 0.15;
    if (isInt) score += 0.18;
    if (isOnline) score += 0.08;
    if (hour < 5 || hour > 22) score += 0.22;
    if (velocity > 5) score += 0.25;
    if (txnData.account_balance_ratio > 0.85) score += 0.15;
    if (txnData.card_age_days < 90) score += 0.12;
    score = Math.min(score + Math.random() * 0.05, 0.99);

    const level = score < 0.3 ? "low" : score < 0.6 ? "medium" : score < 0.85 ? "high" : "critical";

    const shap = [
      { feature: "amount", label: "Transaction Amount ($)", value: amount, shap_value: amount > 1000 ? 0.28 : -0.08, direction: amount > 1000 ? "increases_risk" : "decreases_risk", magnitude: amount > 1000 ? 0.28 : 0.08 },
      { feature: "hour_of_day", label: "Hour of Day", value: hour, shap_value: (hour < 5) ? 0.22 : -0.05, direction: (hour < 5) ? "increases_risk" : "decreases_risk", magnitude: (hour < 5) ? 0.22 : 0.05 },
      { feature: "is_international", label: "International Transaction", value: isInt, shap_value: isInt ? 0.18 : -0.06, direction: isInt ? "increases_risk" : "decreases_risk", magnitude: isInt ? 0.18 : 0.06 },
      { feature: "transaction_velocity_1h", label: "Transactions in Last Hour", value: velocity, shap_value: velocity > 4 ? 0.21 : -0.04, direction: velocity > 4 ? "increases_risk" : "decreases_risk", magnitude: velocity > 4 ? 0.21 : 0.04 },
      { feature: "account_balance_ratio", label: "Balance-to-Limit Ratio", value: txnData.account_balance_ratio, shap_value: txnData.account_balance_ratio > 0.8 ? 0.14 : -0.09, direction: txnData.account_balance_ratio > 0.8 ? "increases_risk" : "decreases_risk", magnitude: txnData.account_balance_ratio > 0.8 ? 0.14 : 0.09 },
      { feature: "card_age_days", label: "Card Age (Days)", value: txnData.card_age_days, shap_value: txnData.card_age_days < 90 ? 0.12 : -0.07, direction: txnData.card_age_days < 90 ? "increases_risk" : "decreases_risk", magnitude: txnData.card_age_days < 90 ? 0.12 : 0.07 },
      { feature: "is_online", label: "Online Transaction", value: isOnline, shap_value: isOnline ? 0.08 : -0.03, direction: isOnline ? "increases_risk" : "decreases_risk", magnitude: isOnline ? 0.08 : 0.03 },
      { feature: "merchant_category_encoded", label: "Merchant Category", value: txnData.merchant_category_encoded, shap_value: -0.04, direction: "decreases_risk", magnitude: 0.04 },
    ].sort((a, b) => b.magnitude - a.magnitude);

    const riskFact = shap.filter(x => x.direction === "increases_risk").slice(0, 3).map(x => x.label);
    const safeFact = shap.filter(x => x.direction === "decreases_risk").slice(0, 2).map(x => x.label);

    const emoji = { low: "✅", medium: "⚠️", high: "🔴", critical: "🚨" }[level];
    const explanation = `${emoji} ${RISK_LABELS[level]} — Score: ${formatPercent(score)}. ` +
      (riskFact.length ? `Risk drivers: ${riskFact.join(", ")}. ` : "") +
      (safeFact.length ? `Mitigating: ${safeFact.join(", ")}.` : "");

    resolve({
      risk_score: score,
      risk_level: level,
      is_fraud: score >= 0.5,
      confidence: 0.85 + Math.random() * 0.1,
      shap_values: shap,
      top_factors: shap.slice(0, 5).map(x => x.label),
      explanation,
      transaction_id: Math.random().toString(36).slice(2, 10).toUpperCase(),
    });
  }, 1400));
}

function mockChat(message) {
  return new Promise(resolve => setTimeout(() => {
    const m = message.toLowerCase();
    let response, txnData = null;

    const amountMatch = message.match(/\$?([\d,]+(?:\.\d{1,2})?)/);

    if (amountMatch) {
      const amount = parseFloat(amountMatch[1].replace(",", ""));
      const isInt = /international|foreign|abroad/i.test(message);
      const isOnline = /online|web|digital|e-?commerce/i.test(message);
      const hourMatch = message.match(/(\d{1,2})\s*(am|pm)/i);
      let hour = 14;
      if (hourMatch) {
        hour = parseInt(hourMatch[1]);
        if (/pm/i.test(hourMatch[2]) && hour < 12) hour += 12;
        hour = hour % 24;
      }
      const velMatch = message.match(/(\d+)\s*transactions?/i);
      const velocity = velMatch ? parseInt(velMatch[1]) : 1;

      txnData = {
        amount, hour_of_day: hour,
        is_international: isInt ? 1 : 0,
        is_online: isOnline ? 1 : 0,
        transaction_velocity_1h: velocity,
        transaction_velocity_24h: velocity * 4,
        merchant_category_encoded: 3,
        day_of_week: 1,
        avg_transaction_amount: amount * 0.6,
        amount_deviation: 1.2,
        card_age_days: 400,
        account_balance_ratio: 0.35,
      };
      response = null; // will be set after analysis
    } else if (/hi|hello|hey|help/i.test(m) && m.split(" ").length < 4) {
      response = {
        message: "👋 **Welcome to the Explainable Fraud Detection System!**\n\nI analyze transactions in real time using ML and explain *why* each decision was made using **SHAP values**.\n\n**Try:**\n• *'Analyze $3,500 international online purchase at 2am'*\n• *'Check $200 grocery store transaction'*\n• *'5 transactions in 1 hour, $800 each'*",
        suggestions: ["Analyze $5,000 international transfer", "Explain fraud patterns", "What is SHAP?", "Check model accuracy"],
      };
    } else if (/shap|explain|why|factor/i.test(m)) {
      response = {
        message: "**SHAP (SHapley Additive exPlanations)** breaks down each prediction:\n\n🔴 Features that **increase** fraud risk push the score up\n🟢 Features that **decrease** fraud risk pull the score down\n\nThe magnitude shows *how much* each feature contributed. This makes the ML model fully transparent — you can see exactly why a transaction was flagged, not just that it was flagged.",
        suggestions: ["Analyze a transaction", "Show common fraud patterns", "How accurate is the model?"],
      };
    } else if (/pattern|common|fraud|typical/i.test(m)) {
      response = {
        message: "**Common Fraud Patterns:**\n\n🌙 **Off-hours** — Transactions at 1–4am\n🌍 **International + online** — Card-not-present fraud\n⚡ **High velocity** — 5+ transactions/hour (bot activity)\n💰 **Amount anomaly** — Far above historical average\n🆕 **New card** — Cards under 90 days old\n📊 **High balance ratio** — Account takeover indicator",
        suggestions: ["Analyze $10,000 wire transfer", "What is SHAP?", "Check model accuracy"],
      };
    } else if (/accura|model|precision|recall/i.test(m)) {
      response = {
        message: "**Model Stats:**\n\n• **Algorithm**: Random Forest (100 trees)\n• **Fraud Recall**: ~92%\n• **Precision**: ~87%\n• **Explainability**: SHAP TreeExplainer (exact)\n• **Training**: 5,000 transactions (5% fraud rate)\n\n⚠️ *Always apply human review for critical flags.*",
        suggestions: ["Analyze a transaction", "Show fraud patterns", "What is SHAP?"],
      };
    } else {
      response = {
        message: "I can **analyze transactions** and explain risk factors. Try describing a transaction:\n\n*'$2,500 international online purchase at 3am with 4 recent transactions'*\n\nOr ask about fraud patterns, model accuracy, or SHAP explainability.",
        suggestions: ["Analyze $1,000 international purchase", "Explain fraud patterns", "What is SHAP?", "Model accuracy"],
      };
    }

    if (txnData) {
      mockAnalyze(txnData).then(result => {
        resolve({ ...result, fromChat: true, txnData });
      });
    } else {
      resolve(response);
    }
  }, 600));
}

// ──────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ──────────────────────────────────────────────────────────────

function RiskGauge({ score, level }) {
  const deg = score * 180;
  const color = riskColor(level);
  const r = 52, cx = 64, cy = 64;
  const circumference = Math.PI * r;
  const strokeLen = (score * circumference);

  return (
    <div style={{ textAlign: "center", padding: "8px 0" }}>
      <svg width={128} height={80} viewBox="0 0 128 80">
        {/* Background arc */}
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke="#1a2d45" strokeWidth={10} strokeLinecap="round" />
        {/* Score arc */}
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke={color} strokeWidth={10} strokeLinecap="round"
          strokeDasharray={`${strokeLen} ${circumference}`}
          style={{ transition: "stroke-dasharray 1s ease", filter: `drop-shadow(0 0 6px ${color})` }}
        />
        {/* Needle */}
        <g transform={`rotate(${deg - 90}, ${cx}, ${cy})`}>
          <line x1={cx} y1={cy} x2={cx} y2={cy - r + 6} stroke={color} strokeWidth={2} strokeLinecap="round" />
        </g>
        <circle cx={cx} cy={cy} r={5} fill={color} />
        {/* Labels */}
        <text x={8} y={74} fill="#4a6580" fontSize={10} fontFamily="Space Mono">0%</text>
        <text x={104} y={74} fill="#4a6580" fontSize={10} fontFamily="Space Mono">100%</text>
      </svg>
      <div style={{ fontFamily: "Space Mono", fontSize: 28, fontWeight: 700, color, lineHeight: 1, marginTop: -4, letterSpacing: -1 }}>
        {(score * 100).toFixed(1)}%
      </div>
      <div style={{ color, fontFamily: "Syne", fontSize: 11, fontWeight: 700, letterSpacing: 4, marginTop: 4, textTransform: "uppercase" }}>
        {RISK_LABELS[level]}
      </div>
    </div>
  );
}

function SHAPBar({ item, maxMag }) {
  const pct = maxMag > 0 ? (item.magnitude / maxMag) * 100 : 0;
  const isRisk = item.direction === "increases_risk";
  const color = isRisk ? "#ff3d5a" : "#00ff88";

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontSize: 11, fontFamily: "Space Mono" }}>
        <span style={{ color: "#c8daf0", maxWidth: "68%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {isRisk ? "▲" : "▼"} {item.label}
        </span>
        <span style={{ color, fontWeight: 700 }}>
          {item.shap_value > 0 ? "+" : ""}{item.shap_value.toFixed(3)}
        </span>
      </div>
      <div style={{ height: 6, background: "#1a2d45", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, background: color,
          borderRadius: 3, boxShadow: `0 0 8px ${color}`,
          transition: "width 0.8s ease",
          animation: "barFill 0.8s ease both",
        }} />
      </div>
    </div>
  );
}

function AnalysisCard({ result }) {
  if (!result) return null;
  const maxMag = result.shap_values?.[0]?.magnitude || 1;
  const color = riskColor(result.risk_level);

  return (
    <div className="fade-up" style={{
      background: "#0d1420",
      border: `1px solid ${color}33`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 8,
      padding: "16px 18px",
      marginTop: 8,
      boxShadow: `0 0 20px ${color}11`,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <RiskGauge score={result.risk_score} level={result.risk_level} />

        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={{ fontFamily: "Space Mono", fontSize: 10, color: "#4a6580", marginBottom: 12, letterSpacing: 2 }}>
            TRANSACTION ID
          </div>
          <div style={{ fontFamily: "Space Mono", fontSize: 13, color: "#00e5ff", marginBottom: 14 }}>
            #{result.transaction_id}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              ["CONFIDENCE", formatPercent(result.confidence)],
              ["VERDICT", result.is_fraud ? "🚨 FRAUD" : "✅ LEGIT"],
            ].map(([label, val]) => (
              <div key={label} style={{
                background: "#111b2a", borderRadius: 6, padding: "8px 10px",
                border: "1px solid #1a2d45",
              }}>
                <div style={{ fontFamily: "Space Mono", fontSize: 9, color: "#4a6580", letterSpacing: 2, marginBottom: 4 }}>{label}</div>
                <div style={{ fontFamily: "Space Mono", fontSize: 12, color: result.is_fraud ? "#ff3d5a" : "#00ff88", fontWeight: 700 }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SHAP breakdown */}
      {result.shap_values?.length > 0 && (
        <div>
          <div style={{ fontFamily: "Space Mono", fontSize: 9, color: "#4a6580", letterSpacing: 3, marginBottom: 12, paddingTop: 12, borderTop: "1px solid #1a2d45" }}>
            SHAP FEATURE ATTRIBUTION
          </div>
          {result.shap_values.slice(0, 7).map((item, i) => (
            <SHAPBar key={item.feature} item={item} maxMag={maxMag} />
          ))}
        </div>
      )}
    </div>
  );
}

function ChatBubble({ msg }) {
  const isUser = msg.role === "user";

  const renderContent = (text) => {
    // Bold markdown
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((p, i) =>
      p.startsWith("**") && p.endsWith("**")
        ? <strong key={i} style={{ color: "#00e5ff" }}>{p.slice(2, -2)}</strong>
        : <span key={i}>{p}</span>
    );
  };

  return (
    <div className="fade-up" style={{
      display: "flex",
      flexDirection: isUser ? "row-reverse" : "row",
      gap: 10,
      marginBottom: 16,
      alignItems: "flex-start",
    }}>
      {/* Avatar */}
      <div style={{
        width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
        background: isUser ? "#00e5ff22" : "#111b2a",
        border: `1px solid ${isUser ? "#00e5ff44" : "#1a2d45"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 14,
      }}>
        {isUser ? "👤" : "🔍"}
      </div>

      <div style={{ maxWidth: "80%", minWidth: 60 }}>
        <div style={{
          background: isUser ? "#00e5ff11" : "#0d1420",
          border: `1px solid ${isUser ? "#00e5ff33" : "#1a2d45"}`,
          borderRadius: isUser ? "12px 2px 12px 12px" : "2px 12px 12px 12px",
          padding: "10px 14px",
          fontFamily: "Syne",
          fontSize: 13.5,
          lineHeight: 1.65,
          color: "#c8daf0",
          whiteSpace: "pre-wrap",
        }}>
          {msg.content.split("\n").map((line, i) => (
            <span key={i}>{renderContent(line)}{i < msg.content.split("\n").length - 1 ? <br /> : null}</span>
          ))}
        </div>

        {/* Timestamp */}
        <div style={{
          fontFamily: "Space Mono", fontSize: 9, color: "#2a4060",
          marginTop: 4, textAlign: isUser ? "right" : "left", letterSpacing: 1,
        }}>
          {new Date(msg.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>

        {/* Analysis card */}
        {msg.analysisResult && <AnalysisCard result={msg.analysisResult} />}
      </div>
    </div>
  );
}

function TransactionForm({ onAnalyze, loading }) {
  const [form, setForm] = useState({
    amount: 1500,
    hour_of_day: 3,
    day_of_week: 1,
    merchant_category_encoded: 9,
    transaction_velocity_1h: 6,
    transaction_velocity_24h: 15,
    avg_transaction_amount: 250,
    is_international: true,
    is_online: true,
    card_age_days: 45,
    account_balance_ratio: 0.88,
  });

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const fieldStyle = {
    background: "#111b2a",
    border: "1px solid #1a2d45",
    borderRadius: 6, padding: "6px 10px",
    color: "#c8daf0", fontFamily: "Space Mono",
    fontSize: 12, width: "100%",
    outline: "none",
  };

  const labelStyle = {
    fontFamily: "Space Mono", fontSize: 9,
    color: "#4a6580", letterSpacing: 2,
    display: "block", marginBottom: 4,
  };

  return (
    <div style={{
      background: "#0d1420",
      border: "1px solid #1a2d45",
      borderRadius: 10, padding: "16px",
    }}>
      <div style={{
        fontFamily: "Space Mono", fontSize: 9,
        color: "#00e5ff", letterSpacing: 4,
        marginBottom: 14, textTransform: "uppercase",
      }}>
        ▶ Transaction Input
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {/* Amount */}
        <div style={{ gridColumn: "1/-1" }}>
          <label style={labelStyle}>AMOUNT ($)</label>
          <input type="number" style={fieldStyle} value={form.amount}
            onChange={e => upd("amount", parseFloat(e.target.value) || 0)} />
        </div>

        {/* Hour */}
        <div>
          <label style={labelStyle}>HOUR (0–23)</label>
          <input type="number" min={0} max={23} style={fieldStyle}
            value={form.hour_of_day} onChange={e => upd("hour_of_day", parseInt(e.target.value) || 0)} />
        </div>

        {/* Merchant */}
        <div>
          <label style={labelStyle}>MERCHANT CATEGORY</label>
          <select style={{ ...fieldStyle, cursor: "pointer" }}
            value={form.merchant_category_encoded}
            onChange={e => upd("merchant_category_encoded", parseInt(e.target.value))}>
            {MERCHANT_CATEGORIES.map((c, i) => (
              <option key={i} value={i}>{c}</option>
            ))}
          </select>
        </div>

        {/* Velocity 1h */}
        <div>
          <label style={labelStyle}>TRANSACTIONS (1H)</label>
          <input type="number" min={0} style={fieldStyle}
            value={form.transaction_velocity_1h}
            onChange={e => upd("transaction_velocity_1h", parseInt(e.target.value) || 0)} />
        </div>

        {/* Velocity 24h */}
        <div>
          <label style={labelStyle}>TRANSACTIONS (24H)</label>
          <input type="number" min={0} style={fieldStyle}
            value={form.transaction_velocity_24h}
            onChange={e => upd("transaction_velocity_24h", parseInt(e.target.value) || 0)} />
        </div>

        {/* Avg amount */}
        <div>
          <label style={labelStyle}>AVG AMOUNT ($)</label>
          <input type="number" style={fieldStyle}
            value={form.avg_transaction_amount}
            onChange={e => upd("avg_transaction_amount", parseFloat(e.target.value) || 0)} />
        </div>

        {/* Card age */}
        <div>
          <label style={labelStyle}>CARD AGE (DAYS)</label>
          <input type="number" min={0} style={fieldStyle}
            value={form.card_age_days}
            onChange={e => upd("card_age_days", parseInt(e.target.value) || 0)} />
        </div>

        {/* Balance ratio */}
        <div>
          <label style={labelStyle}>BALANCE RATIO (0–1)</label>
          <input type="number" min={0} max={1} step={0.01} style={fieldStyle}
            value={form.account_balance_ratio}
            onChange={e => upd("account_balance_ratio", parseFloat(e.target.value) || 0)} />
        </div>

        {/* Toggles */}
        <div style={{ gridColumn: "1/-1", display: "flex", gap: 10 }}>
          {[
            ["is_international", "🌍 INTERNATIONAL"],
            ["is_online", "🌐 ONLINE"],
          ].map(([key, label]) => (
            <button key={key}
              onClick={() => upd(key, !form[key])}
              style={{
                flex: 1, padding: "7px 10px",
                background: form[key] ? "#00e5ff22" : "#111b2a",
                border: `1px solid ${form[key] ? "#00e5ff66" : "#1a2d45"}`,
                borderRadius: 6, color: form[key] ? "#00e5ff" : "#4a6580",
                fontFamily: "Space Mono", fontSize: 10, cursor: "pointer",
                letterSpacing: 1,
                transition: "all 0.2s",
              }}>
              {label} {form[key] ? "ON" : "OFF"}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={() => onAnalyze(form)}
        disabled={loading}
        style={{
          width: "100%", marginTop: 14, padding: "11px",
          background: loading ? "#1a2d45" : "linear-gradient(135deg, #00e5ff22, #00e5ff11)",
          border: `1px solid ${loading ? "#1a2d45" : "#00e5ff66"}`,
          borderRadius: 7, color: loading ? "#4a6580" : "#00e5ff",
          fontFamily: "Syne", fontSize: 13, fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
          letterSpacing: 2, transition: "all 0.2s",
          boxShadow: loading ? "none" : "0 0 20px #00e5ff22",
        }}>
        {loading ? "⏳ ANALYZING..." : "⚡ ANALYZE TRANSACTION"}
      </button>
    </div>
  );
}

function StatPill({ label, value, color }) {
  return (
    <div style={{
      background: "#0d1420", border: "1px solid #1a2d45",
      borderRadius: 8, padding: "10px 14px", textAlign: "center",
    }}>
      <div style={{ fontFamily: "Space Mono", fontSize: 18, fontWeight: 700, color: color || "#00e5ff" }}>
        {value}
      </div>
      <div style={{ fontFamily: "Space Mono", fontSize: 9, color: "#4a6580", marginTop: 3, letterSpacing: 2 }}>
        {label}
      </div>
    </div>
  );
}

function WSStatusDot({ connected }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%",
        background: connected ? "#00ff88" : "#ff3d5a",
        boxShadow: connected ? "0 0 6px #00ff88" : "none",
        animation: connected ? "pulse-border 2s infinite" : "none",
        display: "inline-block",
      }} />
      <span style={{ fontFamily: "Space Mono", fontSize: 9, color: connected ? "#00ff88" : "#ff3d5a", letterSpacing: 2 }}>
        {connected ? "LIVE" : "DEMO"}
      </span>
    </span>
  );
}

// ──────────────────────────────────────────────────────────────
// MAIN APP
// ──────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 1, role: "assistant", ts: Date.now(),
      content: "👋 **Welcome to the Explainable Fraud Detection System!**\n\nI analyze transactions in real time using a Random Forest model with **SHAP explainability** — so you see *exactly why* each decision was made.\n\n**Try asking:**\n• *'Analyze $3,500 international online purchase at 3am'*\n• *'Check $150 grocery store transaction'*\n• *'What patterns indicate fraud?'*\n\nOr use the Transaction Form to run a detailed analysis.",
      analysisResult: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formResult, setFormResult] = useState(null);
  const [wsConnected] = useState(false); // Would be true with backend
  const [stats, setStats] = useState({ total: 0, fraud: 0, avgScore: 0 });
  const [alerts, setAlerts] = useState([]);
  const [suggestions, setSuggestions] = useState([
    "Analyze $5,000 international wire at 2am",
    "What is SHAP explainability?",
    "Show common fraud patterns",
    "Model accuracy stats",
  ]);
  const [activeTab, setActiveTab] = useState("chat");

  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const msgId = useRef(10);

  // Inject CSS
  useEffect(() => {
    const cleanup = injectCSS(CSS);
    return cleanup;
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addAlert = useCallback((level, text) => {
    const id = Date.now();
    setAlerts(a => [{ id, level, text }, ...a].slice(0, 3));
    setTimeout(() => setAlerts(a => a.filter(x => x.id !== id)), 6000);
  }, []);

  const updateStats = useCallback((result) => {
    setStats(prev => {
      const newTotal = prev.total + 1;
      const newFraud = prev.fraud + (result.is_fraud ? 1 : 0);
      const newAvg = (prev.avgScore * prev.total + result.risk_score) / newTotal;
      return { total: newTotal, fraud: newFraud, avgScore: newAvg };
    });
  }, []);

  const sendMessage = async (text) => {
    if (!text.trim() || chatLoading) return;
    const userText = text.trim();
    setInput("");
    setSuggestions([]);

    const userMsg = { id: msgId.current++, role: "user", ts: Date.now(), content: userText, analysisResult: null };
    setMessages(m => [...m, userMsg]);

    setChatLoading(true);
    try {
      const res = await mockChat(userText);

      let assistantContent, analysisResult = null;
      let newSugs = [];

      if (res.fromChat && res.risk_score !== undefined) {
        // Analysis result from chat
        updateStats(res);
        analysisResult = res;
        const riskEmoji = { low: "✅", medium: "⚠️", high: "🔴", critical: "🚨" }[res.risk_level];
        assistantContent = `${riskEmoji} Analysis complete — see breakdown below.`;
        newSugs = ["Why is this flagged?", "Analyze another transaction", "Show fraud patterns"];

        if (res.risk_level === "high" || res.risk_level === "critical") {
          addAlert(res.risk_level, `${RISK_LABELS[res.risk_level]} transaction detected — ${formatPercent(res.risk_score)} risk`);
        }
      } else {
        assistantContent = res.message || "";
        newSugs = res.suggestions || [];
      }

      const botMsg = { id: msgId.current++, role: "assistant", ts: Date.now(), content: assistantContent, analysisResult };
      setMessages(m => [...m, botMsg]);
      setSuggestions(newSugs);
    } finally {
      setChatLoading(false);
    }
  };

  const handleFormAnalyze = async (form) => {
    setFormLoading(true);
    setFormResult(null);
    try {
      const result = await mockAnalyze(form);
      setFormResult(result);
      updateStats(result);
      if (result.risk_level === "high" || result.risk_level === "critical") {
        addAlert(result.risk_level, `${RISK_LABELS[result.risk_level]}: ${formatMoney(form.amount)}`);
      }
    } finally {
      setFormLoading(false);
    }
  };

  // ── Layout ──
  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "var(--bg)", position: "relative", overflow: "hidden",
      fontFamily: "var(--sans)",
    }}>
      {/* Scanline effect */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 999,
        background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
      }} />

      {/* Alerts */}
      <div style={{ position: "fixed", top: 70, right: 16, zIndex: 100, display: "flex", flexDirection: "column", gap: 8 }}>
        {alerts.map(alert => (
          <div key={alert.id} className="fade-up" style={{
            background: "#0d1420",
            border: `1px solid ${alert.level === "critical" ? "#ff0066" : "#ff3d5a"}`,
            borderRadius: 8, padding: "10px 14px",
            boxShadow: `0 0 20px ${alert.level === "critical" ? "#ff006633" : "#ff3d5a33"}`,
            fontFamily: "Space Mono", fontSize: 11, color: "#ff3d5a",
            maxWidth: 280, animation: "alertPulse 1s ease infinite",
          }}>
            🚨 {alert.text}
          </div>
        ))}
      </div>

      {/* Header */}
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid #1a2d45",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "#080c10",
        flexShrink: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 8,
            background: "linear-gradient(135deg, #00e5ff22, #00e5ff08)",
            border: "1px solid #00e5ff44",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17,
          }}>
            🔒
          </div>
          <div>
            <div style={{ fontFamily: "Syne", fontWeight: 800, fontSize: 15, color: "#c8daf0", letterSpacing: 0.5 }}>
              FraudShield
              <span style={{ color: "#00e5ff", marginLeft: 6, fontSize: 11, fontFamily: "Space Mono", fontWeight: 400, letterSpacing: 3 }}>
                XAI
              </span>
            </div>
            <div style={{ fontFamily: "Space Mono", fontSize: 9, color: "#4a6580", letterSpacing: 2 }}>
              EXPLAINABLE FRAUD DETECTION
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Stats pills */}
          <div style={{ display: "flex", gap: 8 }}>
            {[
              ["ANALYZED", stats.total, "#00e5ff"],
              ["FRAUD", stats.fraud, "#ff3d5a"],
              ["AVG RISK", stats.total ? formatPercent(stats.avgScore) : "—", "#ffb800"],
            ].map(([l, v, c]) => (
              <div key={l} style={{
                fontFamily: "Space Mono", fontSize: 10,
                color: c, padding: "4px 10px",
                background: `${c}11`, border: `1px solid ${c}33`,
                borderRadius: 5,
              }}>
                <span style={{ color: "#4a6580", fontSize: 8, letterSpacing: 2 }}>{l} </span>
                {v}
              </div>
            ))}
          </div>
          <WSStatusDot connected={wsConnected} />
        </div>
      </div>

      {/* Tab bar */}
      <div style={{
        display: "flex", borderBottom: "1px solid #1a2d45",
        background: "#080c10", flexShrink: 0,
      }}>
        {[["chat", "💬 Chat"], ["form", "📊 Analyze"]].map(([id, label]) => (
          <button key={id}
            onClick={() => setActiveTab(id)}
            style={{
              padding: "10px 20px",
              background: "none", border: "none",
              borderBottom: activeTab === id ? "2px solid #00e5ff" : "2px solid transparent",
              color: activeTab === id ? "#00e5ff" : "#4a6580",
              fontFamily: "Syne", fontSize: 13, fontWeight: 600,
              cursor: "pointer", transition: "all 0.2s",
              letterSpacing: 0.5,
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {activeTab === "chat" ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Messages */}
            <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px 8px" }}>
              {messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)}

              {/* Typing indicator */}
              {chatLoading && (
                <div className="fade-up" style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "flex-start" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#111b2a", border: "1px solid #1a2d45", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🔍</div>
                  <div style={{ background: "#0d1420", border: "1px solid #1a2d45", borderRadius: "2px 12px 12px 12px", padding: "12px 16px" }}>
                    <div style={{ display: "flex", gap: 4 }}>
                      {[0, 1, 2].map(i => (
                        <div key={i} style={{
                          width: 6, height: 6, borderRadius: "50%",
                          background: "#00e5ff", opacity: 0.6,
                          animation: `blink 1.2s ease ${i * 0.2}s infinite`,
                        }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Suggestions */}
            {suggestions.length > 0 && (
              <div style={{ padding: "0 16px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
                {suggestions.map((s, i) => (
                  <button key={i}
                    onClick={() => sendMessage(s)}
                    style={{
                      padding: "5px 11px",
                      background: "#0d1420", border: "1px solid #1a2d45",
                      borderRadius: 20, color: "#4a6580",
                      fontFamily: "Syne", fontSize: 11, cursor: "pointer",
                      transition: "all 0.2s",
                    }}
                    onMouseEnter={e => { e.target.style.borderColor = "#00e5ff44"; e.target.style.color = "#00e5ff"; }}
                    onMouseLeave={e => { e.target.style.borderColor = "#1a2d45"; e.target.style.color = "#4a6580"; }}>
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            <div style={{
              padding: "12px 16px",
              borderTop: "1px solid #1a2d45",
              display: "flex", gap: 10,
              background: "#080c10", flexShrink: 0,
            }}>
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
                placeholder="Describe a transaction or ask about fraud patterns..."
                style={{
                  flex: 1, padding: "10px 14px",
                  background: "#0d1420", border: "1px solid #1a2d45",
                  borderRadius: 8, color: "#c8daf0",
                  fontFamily: "Syne", fontSize: 13,
                  outline: "none", transition: "border-color 0.2s",
                }}
                onFocus={e => e.target.style.borderColor = "#00e5ff44"}
                onBlur={e => e.target.style.borderColor = "#1a2d45"}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={chatLoading || !input.trim()}
                style={{
                  padding: "10px 18px",
                  background: chatLoading || !input.trim() ? "#0d1420" : "#00e5ff22",
                  border: `1px solid ${chatLoading || !input.trim() ? "#1a2d45" : "#00e5ff44"}`,
                  borderRadius: 8, color: chatLoading || !input.trim() ? "#4a6580" : "#00e5ff",
                  fontFamily: "Syne", fontWeight: 700, fontSize: 13,
                  cursor: chatLoading || !input.trim() ? "not-allowed" : "pointer",
                  transition: "all 0.2s",
                }}>
                ▶
              </button>
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
            <TransactionForm onAnalyze={handleFormAnalyze} loading={formLoading} />
            {formLoading && (
              <div style={{ textAlign: "center", padding: 24, color: "#00e5ff", fontFamily: "Space Mono", fontSize: 12 }}>
                <div style={{
                  width: 24, height: 24, border: "2px solid #00e5ff33",
                  borderTop: "2px solid #00e5ff", borderRadius: "50%",
                  animation: "spin 0.8s linear infinite",
                  margin: "0 auto 12px",
                }} />
                Running ML analysis + SHAP explanations...
              </div>
            )}
            {formResult && <AnalysisCard result={formResult} />}
            {formResult && (
              <div style={{
                background: "#0d1420", border: "1px solid #1a2d45",
                borderRadius: 10, padding: 16,
              }}>
                <div style={{ fontFamily: "Space Mono", fontSize: 9, color: "#4a6580", letterSpacing: 3, marginBottom: 12 }}>
                  EXPLANATION
                </div>
                <p style={{ fontFamily: "Syne", fontSize: 13.5, lineHeight: 1.7, color: "#c8daf0" }}>
                  {formResult.explanation}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
