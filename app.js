"use strict";

const selector = document.getElementById("class-year");
const statusMessage = document.getElementById("status");
const results = document.getElementById("results");
const number = new Intl.NumberFormat("en-US");
const serviceLabels = { USN: "U.S. Navy", USMC: "U.S. Marine Corps", other: "Other U.S. services" };
let chart;
let requestId = 0;

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Unable to load ${path}`);
  return response.json();
}

function text(id, value) {
  document.getElementById(id).textContent = value;
}

function renderVoluntary(data) {
  const reports = data.voluntary;
  const stillIn = reports.reported_still_in;
  text("voluntary-summary", `${number.format(stillIn)} still-in and ${number.format(reports.reported_out)} out respondents accepted${reports.as_of ? ` · aggregate updated ${reports.as_of}` : " · no submissions included"}.`);
  document.getElementById("rank-empty").hidden = stillIn > 0;
  document.getElementById("rank-table-wrap").hidden = stillIn === 0;
  const rows = document.getElementById("rank-rows");
  rows.replaceChildren();
  for (const entry of reports.rank_distribution) {
    if (!entry.count) continue;
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = entry.rank;
    const count = document.createElement("td");
    count.textContent = number.format(entry.count);
    const share = document.createElement("td");
    share.textContent = `${entry.percent.toFixed(1)}% `;
    const bar = document.createElement("progress");
    bar.max = 100;
    bar.value = entry.percent;
    bar.setAttribute("aria-label", `${entry.rank}: ${entry.percent}% of still-in respondents`);
    share.append(bar);
    row.append(heading, count, share);
    rows.append(row);
  }
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
    await loadClass(selector.value);
  } catch {
    selector.replaceChildren(new Option("Classes unavailable", ""));
    statusMessage.textContent = "The class index could not be loaded. Please reload to try again.";
  }
}

initialize();
