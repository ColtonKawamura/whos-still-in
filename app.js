"use strict";

const selector = document.getElementById("class-year");
const statusMessage = document.getElementById("status");
const results = document.getElementById("results");
const number = new Intl.NumberFormat("en-US");
const serviceLabels = {
  USN: "U.S. Navy", USMC: "U.S. Marine Corps", USA: "U.S. Army", USAF: "U.S. Air Force",
  USSF: "U.S. Space Force", USCG: "U.S. Coast Guard", other: "Other U.S. services",
};
const statusLabels = { still_in: "Still in", out: "Out" };
const dimensions = {
  community: { label: "Warfare community", filter: "filter-community" },
  status: { label: "Serving status", filter: "filter-status" },
  service: { label: "Current / last service", filter: "filter-service" },
  current_rank: { label: "Current pay grade (still in)", filter: "filter-current-rank", only: "still_in" },
  separation_rank: { label: "Pay grade at separation (out)", filter: "filter-separation-rank", only: "out" },
  industry: { label: "Current industry (out)", filter: "filter-industry", only: "out" },
};
const palette = ["#00205B", "#C5B783", "#4A6FA5", "#74632F", "#8FA9D1", "#2E3B4E", "#E2D6A8", "#5C7C99", "#A38F4D", "#B8C4D6"];
let chart;
let exploreChart;
let explore;
let requestId = 0;

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Unable to load ${path}`);
  return response.json();
}

function text(id, value) {
  document.getElementById(id).textContent = value;
}

function renderDistribution(tbodyId, entries, key, group) {
  const rows = document.getElementById(tbodyId);
  rows.replaceChildren();
  for (const entry of entries) {
    if (!entry.count) continue;
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = entry[key];
    const count = document.createElement("td");
    count.textContent = number.format(entry.count);
    const share = document.createElement("td");
    share.textContent = `${entry.percent.toFixed(1)}% `;
    const bar = document.createElement("progress");
    bar.max = 100;
    bar.value = entry.percent;
    bar.setAttribute("aria-label", `${entry[key]}: ${entry.percent}% of ${group} respondents`);
    share.append(bar);
    row.append(heading, count, share);
    rows.append(row);
  }
}

function renderVoluntary(data) {
  const reports = data.voluntary;
  const stillIn = reports.reported_still_in;
  const out = reports.reported_out;
  text("voluntary-summary", `${number.format(stillIn)} still-in and ${number.format(out)} out respondents accepted${reports.as_of ? ` · aggregate updated ${reports.as_of}` : " · no submissions included"}.`);
  document.getElementById("rank-empty").hidden = stillIn > 0;
  document.getElementById("rank-table-wrap").hidden = stillIn === 0;
  renderDistribution("rank-rows", reports.rank_distribution, "rank", "still-in");
  document.getElementById("out-empty").hidden = out > 0;
  for (const id of ["highest-rank-table-wrap", "industry-table-wrap"]) {
    document.getElementById(id).hidden = out === 0;
  }
  renderDistribution("highest-rank-rows", reports.highest_rank_distribution, "rank", "out");
  renderDistribution("industry-rows", reports.industry_distribution, "industry", "out");
  setupExplorer(reports);
}

function valuesOf(response, dimension) {
  if (dimension === "community") return response.communities;
  const only = dimensions[dimension].only;
  if (only && response.status !== only) return [];
  const value = dimension.endsWith("_rank") ? response.rank : response[dimension];
  return value === null || value === undefined ? [] : [value];
}

function labelFor(dimension, value) {
  if (dimension === "status") return statusLabels[value] || value;
  if (dimension === "service") return serviceLabels[value] || value;
  return value;
}

function orderedValues(dimension) {
  const present = new Set(explore.responses.flatMap((response) => valuesOf(response, dimension)));
  const canonical = explore.order[dimension] || [...present].sort((a, b) =>
    labelFor(dimension, a).localeCompare(labelFor(dimension, b)));
  return canonical.filter((value) => present.has(value));
}

function fillSelect(select, options, value) {
  select.replaceChildren(...options.map(([optionValue, label]) => new Option(label, optionValue)));
  select.value = options.some(([optionValue]) => optionValue === value) ? value : options[0][0];
}

function setupExplorer(reports) {
  const responses = Array.isArray(reports.responses) ? reports.responses : [];
  explore = {
    responses,
    order: {
      status: ["still_in", "out"],
      current_rank: reports.rank_distribution.map((entry) => entry.rank),
      separation_rank: reports.highest_rank_distribution.map((entry) => entry.rank),
      community: (reports.community_distribution || []).map((entry) => entry.community),
      industry: reports.industry_distribution.map((entry) => entry.industry),
    },
  };
  document.getElementById("explore-empty").hidden = responses.length > 0;
  document.getElementById("explore-body").hidden = responses.length === 0;
  if (!responses.length) {
    if (exploreChart) exploreChart.destroy();
    exploreChart = undefined;
    return;
  }
  for (const [dimension, config] of Object.entries(dimensions)) {
    if (!config.filter) continue;
    fillSelect(document.getElementById(config.filter),
      [["", "All"], ...orderedValues(dimension).map((value) => [value, labelFor(dimension, value)])], "");
  }
  const choices = Object.entries(dimensions).map(([key, config]) => [key, config.label]);
  fillSelect(document.getElementById("breakdown"), choices, "community");
  fillSelect(document.getElementById("split"), [["", "Nothing (totals only)"], ...choices], "status");
  updateExplorer();
}

function filteredResponses() {
  const filters = Object.entries(dimensions)
    .filter(([, config]) => config.filter)
    .map(([dimension, config]) => [dimension, document.getElementById(config.filter).value])
    .filter(([, value]) => value);
  return {
    filters,
    responses: explore.responses.filter((response) =>
      filters.every(([dimension, value]) => valuesOf(response, dimension).includes(value))),
  };
}

function updateExplorer() {
  const breakdown = document.getElementById("breakdown").value;
  let split = document.getElementById("split").value;
  if (split === breakdown) split = "";
  const { filters, responses } = filteredResponses();
  const total = responses.reduce((sum, response) => sum + response.count, 0);
  const percent = document.getElementById("show-as").value === "percent";
  const categories = orderedValues(breakdown);
  const notApplicable = split && dimensions[split].only
    ? `Not applicable (${statusLabels[dimensions[split].only === "out" ? "still_in" : "out"].toLowerCase()})`
    : "Not applicable";
  const splitOf = (response) => {
    if (!split) return [""];
    const values = valuesOf(response, split);
    return values.length ? values : [notApplicable];
  };
  const splitValues = split ? [...orderedValues(split), notApplicable] : [""];
  const counts = new Map(categories.map((category) => [category, new Map(splitValues.map((value) => [value, 0]))]));
  let without = 0;
  for (const response of responses) {
    const values = valuesOf(response, breakdown);
    if (!values.length) without += response.count;
    for (const category of values) {
      for (const splitValue of splitOf(response)) {
        const row = counts.get(category);
        row.set(splitValue, row.get(splitValue) + response.count);
      }
    }
  }
  const totals = new Map(categories.map((category) => [category,
    responses.filter((response) => valuesOf(response, breakdown).includes(category))
      .reduce((sum, response) => sum + response.count, 0)]));
  const shown = categories.filter((category) => totals.get(category) > 0);
  const shownSplit = splitValues.filter((value) => shown.some((category) => counts.get(category).get(value) > 0));

  const filterText = filters.length
    ? ` matching ${filters.map(([dimension, value]) => labelFor(dimension, value)).join(" + ")}`
    : "";
  let summary = `${number.format(total)} respondent${total === 1 ? "" : "s"}${filterText}.`;
  const only = dimensions[breakdown].only;
  if (only && without) {
    const excluded = statusLabels[only === "out" ? "still_in" : "out"].toLowerCase();
    summary += ` ${number.format(without)} ${excluded} respondent${without === 1 ? " is" : "s are"} not included in the ${dimensions[breakdown].label.toLowerCase()} breakdown.`;
  }
  if (breakdown === "community" || split === "community") summary += " Respondents with multiple communities appear in each one.";
  text("explore-summary", summary);

  const head = document.createElement("tr");
  for (const label of [dimensions[breakdown].label, ...(split ? shownSplit.map((value) => labelFor(split, value)) : []), "Respondents", "Share"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    head.append(cell);
  }
  document.getElementById("explore-head").replaceChildren(head);
  const base = total - without;
  const share = (value) => base ? `${(100 * value / base).toFixed(1)}%` : "—";
  document.getElementById("explore-rows").replaceChildren(...shown.map((category) => {
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = labelFor(breakdown, category);
    row.append(heading);
    const values = [
      ...(split ? shownSplit.map((value) => {
        const count = counts.get(category).get(value);
        return percent ? share(count) : number.format(count);
      }) : []),
      number.format(totals.get(category)),
      share(totals.get(category)),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  }));

  const canvas = document.getElementById("explore-chart");
  const wrap = canvas.parentElement;
  const note = document.getElementById("explore-chart-note");
  wrap.style.height = `${Math.max(180, shown.length * 34 + 80)}px`;
  canvas.setAttribute("aria-label", `Voluntary respondents by ${dimensions[breakdown].label.toLowerCase()}${split ? `, split by ${dimensions[split].label.toLowerCase()}` : ""}. Figures are also shown in the table below.`);
  const datasets = shownSplit.map((value) => ({
    label: split ? labelFor(split, value) : "Respondents",
    data: shown.map((category) => {
      const count = counts.get(category).get(value);
      return percent ? (base ? Math.round(1000 * count / base) / 10 : 0) : count;
    }),
    backgroundColor: palette[splitValues.indexOf(value) % palette.length],
  }));
  wrap.hidden = shown.length === 0;
  note.hidden = true;
  try {
    if (typeof Chart === "undefined") throw new Error("Chart library unavailable");
    if (exploreChart) exploreChart.destroy();
    exploreChart = new Chart(canvas, {
      type: "bar",
      data: { labels: shown.map((category) => labelFor(breakdown, category)), datasets },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : undefined,
        scales: {
          x: {
            stacked: true, beginAtZero: true, ticks: percent ? { callback: (value) => `${value}%` } : { precision: 0 },
            title: { display: true, text: percent ? "Share of respondents in the breakdown" : "Respondents" },
          },
          y: { stacked: true },
        },
        plugins: {
          legend: { display: Boolean(split) },
          tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${percent ? `${context.raw}%` : number.format(context.raw)}` } },
        },
        onHover: (event, elements) => {
          event.native.target.style.cursor = elements.length ? "pointer" : "default";
        },
        onClick: (event, elements) => {
          if (!elements.length) return;
          drillDown(breakdown, shown[elements[0].index]);
        },
      },
    });
  } catch {
    wrap.hidden = true;
    note.hidden = false;
  }
}

function drillDown(dimension, value) {
  document.getElementById(dimensions[dimension].filter).value = value;
  const breakdown = document.getElementById("breakdown");
  const next = Object.keys(dimensions).find((key) =>
    key !== dimension && !document.getElementById(dimensions[key].filter).value);
  if (next) breakdown.value = next;
  updateExplorer();
}

function render(data) {
  text("class-title", `Class of ${data.year}`);
  text("confidence", data.confidence);
  text("coverage-note", data.coverage_note);
  text("percent-in", `${data.percent_in.toFixed(1)}%`);
  text("percent-out", `${data.percent_out.toFixed(1)}%`);
  text("count-in", `${number.format(data.estimated_still_in)} classmates (estimated)`);
  text("count-out", `${number.format(data.estimated_out)} classmates (estimated)`);
  text("total", number.format(data.commissioned_total));
  text("as-of", data.as_of);
  document.getElementById("as-of").dateTime = data.as_of;
  text("method", data.method);
  renderVoluntary(data);
  document.getElementById("report-link").href =
    `https://github.com/ColtonKawamura/whos-still-in/issues/new?template=voluntary-report.yml&title=${encodeURIComponent(`[Voluntary report] Class of ${data.year}`)}`;

  const rows = document.getElementById("service-rows");
  rows.replaceChildren();
  for (const [service, counts] of Object.entries(data.by_service)) {
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = serviceLabels[service] || service;
    row.append(heading);
    for (const value of [
      number.format(counts.commissioned),
      number.format(counts.estimated_still_in),
      number.format(counts.estimated_out),
      `${(counts.assumed_retention_rate * 100).toFixed(1)}%`,
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    rows.append(row);
  }

  const sources = document.getElementById("sources");
  sources.replaceChildren();
  for (const source of data.sources) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    const url = new URL(source.url);
    if (!["https:", "http:"].includes(url.protocol)) continue;
    link.href = url.href;
    link.textContent = source.title;
    item.append(link);
    sources.append(item);
  }

  if (chart) {
    chart.destroy();
    chart = undefined;
  }
  const canvas = document.getElementById("status-chart");
  const chartWrap = canvas.parentElement;
  const note = document.getElementById("chart-note");
  canvas.setAttribute("aria-label", `Class of ${data.year}: estimated ${data.percent_in}% still in and ${data.percent_out}% out.`);
  chartWrap.hidden = false;
  note.hidden = true;
  try {
    if (typeof Chart === "undefined") throw new Error("Chart library unavailable");
    chart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Still in (estimated)", "Out (estimated)"],
        datasets: [{
          data: [data.estimated_still_in, data.estimated_out],
          backgroundColor: ["#00205B", "#C5B783"],
          borderColor: "#ffffff",
          borderWidth: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : undefined,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `${context.label}: ${number.format(context.raw)} (${(context.raw / data.commissioned_total * 100).toFixed(1)}%)`,
            },
          },
        },
      },
    });
  } catch {
    chartWrap.hidden = true;
    note.hidden = false;
  }
}

async function loadClass(year) {
  const currentRequest = ++requestId;
  results.hidden = true;
  statusMessage.hidden = false;
  statusMessage.textContent = "Loading class data…";
  try {
    const data = await fetchJson(`data/${year}.json`);
    if (currentRequest !== requestId) return;
    render(data);
    results.hidden = false;
    statusMessage.hidden = true;
  } catch {
    if (currentRequest !== requestId) return;
    statusMessage.textContent = "Class data could not be loaded. Please select another class or reload to try again.";
  }
}

async function initialize() {
  try {
    const index = await fetchJson("data/index.json");
    if (!Array.isArray(index.years) || !index.years.length ||
        !index.years.every((year) => Number.isInteger(year) && year >= 1845 && year <= 9999)) {
      throw new Error("Invalid class index");
    }
    selector.replaceChildren();
    for (const year of index.years) {
      const option = document.createElement("option");
      option.value = year;
      option.textContent = `Class of ${year}`;
      selector.append(option);
    }
    selector.value = index.years.includes(2012) ? "2012" : String(index.years[0]);
    selector.disabled = false;
    selector.addEventListener("change", () => loadClass(selector.value));
    const controls = document.getElementById("explore-controls");
    controls.addEventListener("change", () => updateExplorer());
    controls.addEventListener("submit", (event) => event.preventDefault());
    controls.addEventListener("reset", (event) => {
      event.preventDefault();
      for (const config of Object.values(dimensions)) {
        document.getElementById(config.filter).value = "";
      }
      document.getElementById("show-as").value = "count";
      document.getElementById("breakdown").value = "community";
      document.getElementById("split").value = "status";
      updateExplorer();
    });
    await loadClass(selector.value);
  } catch {
    selector.replaceChildren(new Option("Classes unavailable", ""));
    statusMessage.textContent = "The class index could not be loaded. Please reload to try again.";
  }
}

initialize();
