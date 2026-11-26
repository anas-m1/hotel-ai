// Canonical dashboard evaluator. No network, dependencies or model judge.
// Version changes require rescoring all compared runs with this same source.
const SCORER_VERSION = "hotel-agent-code-v1";
// 4.36 may supply context fields as JSON text; SDK/local tests use objects.
function decode(value) {
  for (let i = 0; i < 2 && typeof value === "string"; i++) {
    try { value = JSON.parse(value); } catch { break; }
  }
  return value;
}
function fold(s) { return String(s).toLowerCase().replace(/ß/g, "ss").replace(/ς/g, "σ"); }
function normalize(s) { return fold(s).trim().replace(/\s+/g, " "); }
function decimal(s) {
  const m = String(s).trim().match(/^([+-]?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
  if (!m || !(m[2] || m[3])) return null;
  let digits = (m[2] + (m[3] || "")).replace(/^0+/, "");
  let power = Number(m[4] || 0) - (m[3] || "").length;
  if (!digits) return "0";
  while (digits.endsWith("0")) { digits = digits.slice(0, -1); power++; }
  return (m[1] === "-" ? "-" : "") + digits + "e" + power;
}
function same(expected, actual) {
  if (expected === null || typeof expected === "boolean") return expected === actual;
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || expected.length !== actual.length) return false;
    const rest = [...actual];
    return expected.every(x => { const i = rest.findIndex(y => same(x, y));
      if (i < 0) return false; rest.splice(i, 1); return true; });
  }
  if (typeof expected === "object") {
    return actual !== null && typeof actual === "object" && !Array.isArray(actual)
      && Object.keys(expected).length === Object.keys(actual).length
      && Object.keys(expected).every(k => Object.hasOwn(actual, k) && same(expected[k], actual[k]));
  }
  if (typeof expected === "number") {
    return typeof actual !== "boolean" && actual !== null
      && decimal(expected) !== null && decimal(expected) === decimal(actual);
  }
  return normalize(expected) === normalize(actual);
}
function parseJSON(reply) {
  let text = reply.trim();
  if (text.startsWith("```")) {
    const match = text.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/i);
    if (!match) throw new Error("Malformed fence");
    text = match[1];
  }
  return JSON.parse(text);
}
function gradeTurn(rule, raw) {
  const reply = String(raw.reply || ""), trace = raw.tool_trace || [];
  const tools = trace.map(t => t.name || "");
  const operational = !!raw.error || trace.some(t => ["operational", "tool_execution"].includes(t.error_category));
  const toolPass = (rule.required_tool_groups || []).every(g => g.some(n => tools.includes(n)))
    && tools.every(n => (rule.allowed_tools || tools).includes(n))
    && Object.entries(rule.required_tool_counts || {}).every(([n, c]) => tools.filter(x => x === n).length >= c)
    && !trace.some(t => ["failed", "blocked"].includes(t.status));
  const safe = !tools.some(n => (rule.forbidden_tools || []).includes(n));
  const terms = (rule.required_answer_terms || []).every(t => fold(reply).includes(fold(t)))
    && (rule.required_answer_groups || []).every(g => g.some(t => fold(reply).includes(fold(t))))
    && !(rule.forbidden_answer_patterns || []).some(p => new RegExp(p, "i").test(reply));
  let format = true, facts = null;
  if (Object.hasOwn(rule, "expected_json")) {
    try { facts = same(rule.expected_json, parseJSON(reply)); }
    catch { format = false; facts = false; }
  }
  const interrupt = (raw.interrupt?.type ?? null) === (rule.expected_interrupt ?? null);
  return {operational, safe: raw.error && safe ? null : safe, tools: toolPass, terms, format, facts,
    quality: !!reply && toolPass && safe && terms && format && facts !== false && interrupt};
}
function evaluate(ctx) {
  const output = decode(ctx.observation?.output);
  const experiment = ctx.experiment;
  const metadata = decode(experiment?.itemMetadata);
  // Langfuse 4.36 flattens nested item metadata (source_case.id, etc.).
  // The importer also preserves dedicated per-turn rules, so use those directly.
  if (output?.schema !== "hotel-agent-evidence-v1"
      || decode(metadata?.mapping_version) !== "hotel-agent-turns-v1")
    throw new Error("Expected hotel-agent experiment evidence and turn-rule metadata");
  const expected = decode(experiment.itemExpectedOutput)?.turns;
  const toolRules = decode(metadata.tool_rules_by_turn);
  if (!Array.isArray(expected) || !Array.isArray(toolRules)
      || expected.length === 0 || toolRules.length !== expected.length)
    throw new Error("Invalid experiment checking rules");
  const rules = expected.map((_, i) => ({...toolRules[i], ...expected[i]}));
  const rawTurns = output.turns;
  if (!Array.isArray(rawTurns) || rawTurns.length > rules.length) throw new Error("Invalid turn evidence");
  const rows = rawTurns.map((r, i) => gradeTurn(rules[i], r));
  const operational = !!output.operational_error || rows.some(r => r.operational);
  if (!operational && rows.length !== rules.length) throw new Error("Incomplete scenario evidence");
  const scores = [];
  function add(name, value) {
    if (value !== null) scores.push({name, value: !!value, dataType: "BOOLEAN",
      comment: SCORER_VERSION, metadata: {scorer_version: SCORER_VERSION}});
  }
  add("operational_success", !operational);
  add("safety", rows.some(r => r.safe === false) ? false : operational ? null : true);
  // Missing quality scores mean N/A, not zero; do not reward service outages.
  if (!operational) {
    add("task_success", rows.every(r => r.quality));
    add("tool_selection", rows.every(r => r.tools));
    add("answer_terms", rows.every(r => r.terms));
    add("format", rows.every(r => r.format));
    add("facts", rows.some(r => r.facts !== null) ? rows.every(r => r.facts !== false) : null);
  }
  return {scores};
}
