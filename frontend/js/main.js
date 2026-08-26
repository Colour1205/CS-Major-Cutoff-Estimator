// Fetches predictions from the backend API and renders them.
const API_BASE_URL = "http://localhost:5000";
const DAILY_MS = 24 * 60 * 60 * 1000;

// Our `year` is the Fall start of the academic year (e.g. 2024 means Fall
// 2024 - Winter 2025) — spelled out everywhere it's shown so it's never
// mistaken for a single calendar year. Standard academic-year shorthand:
// "2024-25", not the full "2024-2025".
function formatSchoolYear(year) {
    return `${year}-${String(year + 1).slice(-2)}`;
}

async function loadEstimate(endpoint, elementId, valueKey) {
    const el = document.getElementById(elementId);
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        if (!response.ok) throw new Error(`request failed: ${response.status}`);
        const data = await response.json();
        el.textContent = data[valueKey].toFixed(1);
    } catch (err) {
        el.textContent = "—";
        console.error(`Failed to load ${endpoint}:`, err);
    }
}

let historyChart = null;

async function loadHistoryChart() {
    try {
        const [history, cutoffEstimate, safeEstimate] = await Promise.all([
            fetch(`${API_BASE_URL}/api/history`).then((r) => r.json()),
            fetch(`${API_BASE_URL}/api/estimate`).then((r) => r.json()),
            fetch(`${API_BASE_URL}/api/estimate/safe`).then((r) => r.json()),
        ]);

        const years = history.map((row) => row.year);
        const estimateYear = cutoffEstimate.year;
        // Only append the estimate year if it's genuinely beyond the
        // historical data (it always should be, but this guards against
        // the estimate ever landing on an already-charted year).
        const labels = years.includes(estimateYear) ? years : [...years, estimateYear];

        const lastHistoryIndex = years.length - 1;
        const estimateIndex = labels.indexOf(estimateYear);

        // A dashed "bridge" dataset: null everywhere except the last real
        // point (so the dash starts exactly where the solid line ends) and
        // the new estimated point — Chart.js draws a line straight through
        // the nulls' gaps only where both segment ends are non-null.
        function bridgeSeries(lastRealValue, estimateValue) {
            const series = labels.map(() => null);
            series[lastHistoryIndex] = lastRealValue;
            series[estimateIndex] = estimateValue;
            return series;
        }

        const chartData = {
            labels: labels.map(formatSchoolYear),
            datasets: [
                {
                    label: "Actual cutoff",
                    data: history.map((row) => row.actual_cutoff),
                    borderColor: "#1f77b4",
                    backgroundColor: "#1f77b4",
                },
                {
                    label: "Estimated cutoff",
                    data: bridgeSeries(history[lastHistoryIndex].actual_cutoff, cutoffEstimate.estimated_cutoff),
                    borderColor: "#1f77b4",
                    backgroundColor: "#1f77b4",
                    borderDash: [6, 4],
                },
                {
                    label: "Safe grade",
                    data: history.map((row) => row.safe_grade),
                    borderColor: "#2ca02c",
                    backgroundColor: "#2ca02c",
                },
                {
                    label: "Estimated safe grade",
                    data: bridgeSeries(history[lastHistoryIndex].safe_grade, safeEstimate.estimated_safe_grade),
                    borderColor: "#2ca02c",
                    backgroundColor: "#2ca02c",
                    borderDash: [6, 4],
                },
            ],
        };

        if (historyChart) {
            // Update the existing chart in place (e.g. on the daily
            // refresh) rather than creating a second Chart bound to the
            // same canvas, which Chart.js rejects.
            historyChart.data = chartData;
            historyChart.update();
            return;
        }

        historyChart = new Chart(document.getElementById("history-chart"), {
            type: "line",
            data: chartData,
            options: {
                scales: { y: { title: { display: true, text: "Average (%)" } } },
                // The dashed "Estimated ..." datasets are visible on the
                // chart, but their own legend entries are redundant — the
                // dashed style already reads as "estimate" once paired with
                // the matching solid-line color.
                plugins: {
                    legend: {
                        labels: { filter: (item) => !item.text.startsWith("Estimated") },
                    },
                },
            },
        });
    } catch (err) {
        console.error("Failed to load history/estimate for chart:", err);
    }
}

async function loadBacktestTable() {
    const tbody = document.querySelector("#backtest-table tbody");
    try {
        const response = await fetch(`${API_BASE_URL}/api/backtest`);
        if (!response.ok) throw new Error(`request failed: ${response.status}`);
        const { results } = await response.json();

        tbody.innerHTML = "";
        for (const row of results) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${formatSchoolYear(row.year)}</td><td>${row.actual.toFixed(1)}</td>` +
                `<td>${row.predicted.toFixed(2)}</td><td>${row.error > 0 ? "+" : ""}${row.error.toFixed(2)}</td>`;
            tbody.appendChild(tr);
        }
    } catch (err) {
        console.error("Failed to load /api/backtest:", err);
    }
}

function refreshAll() {
    loadEstimate("/api/estimate", "cutoff-grade", "estimated_cutoff");
    loadEstimate("/api/estimate/safe", "safe-grade", "estimated_safe_grade");
    loadHistoryChart();
    loadBacktestTable();
}

refreshAll();
setInterval(refreshAll, DAILY_MS);

// --- Submit-mark modal ---

const modalBackdrop = document.getElementById("submit-mark-modal-backdrop");
const submitForm = document.getElementById("submit-mark-form");
const yearInput = document.getElementById("submit-year");
const csc148Input = document.getElementById("submit-csc148");
const csc165Input = document.getElementById("submit-csc165");
const averageInput = document.getElementById("submit-average");
const errorEl = document.getElementById("submit-mark-error");

// The school year range to offer: 2021-2022 (oldest we have any data for)
// through whichever school year has most recently started. UofT's Fall
// term starts September 1st, so the range's upper end advances on its own
// as real time passes — no manual bump needed.
const MIN_SCHOOL_YEAR = 2021;
function currentSchoolYearStart() {
    const now = new Date();
    return now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1; // getMonth() is 0-indexed; 8 = September
}
const maxSchoolYear = currentSchoolYearStart();

for (let year = MIN_SCHOOL_YEAR; year <= maxSchoolYear; year++) {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = formatSchoolYear(year);
    yearInput.appendChild(option);
}
yearInput.value = String(maxSchoolYear);

function openModal() {
    submitForm.reset();
    yearInput.value = String(maxSchoolYear); // form.reset() can revert this on some browsers; reassert explicitly
    errorEl.textContent = "";
    modalBackdrop.classList.add("open");
}

function closeModal() {
    modalBackdrop.classList.remove("open");
}

document.getElementById("submit-mark-btn").addEventListener("click", openModal);
document.getElementById("submit-mark-cancel").addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeModal();
});

// Auto-fill the average once both csc148 and csc165 are entered, so the
// common case (someone has both marks) needs no extra typing.
function autoFillAverage() {
    const csc148 = parseFloat(csc148Input.value);
    const csc165 = parseFloat(csc165Input.value);
    if (!Number.isNaN(csc148) && !Number.isNaN(csc165)) {
        averageInput.value = ((csc148 + csc165) / 2).toFixed(1);
    }
}
csc148Input.addEventListener("input", autoFillAverage);
csc165Input.addEventListener("input", autoFillAverage);

submitForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";

    const csc148 = csc148Input.value === "" ? null : parseFloat(csc148Input.value);
    const csc165 = csc165Input.value === "" ? null : parseFloat(csc165Input.value);
    const average = averageInput.value === "" ? null : parseFloat(averageInput.value);

    // Exactly one of csc148/csc165 filled in, with no average to fall back
    // on, isn't enough to compute a combined grade — same rule the backend
    // enforces, checked here first so the user gets an immediate message.
    const onlyOneCourseGrade = (csc148 !== null) !== (csc165 !== null);
    if (onlyOneCourseGrade && average === null) {
        errorEl.textContent = "Enter both CSC148 and CSC165, or fill in the average.";
        return;
    }
    if (csc148 === null && csc165 === null && average === null) {
        errorEl.textContent = "Enter your average, or both CSC148 and CSC165.";
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/submissions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ year: parseInt(yearInput.value, 10), csc148, csc165, average }),
        });
        const data = await response.json();
        if (!response.ok) {
            errorEl.textContent = data.error || "Submission failed.";
            return;
        }
        closeModal();
    } catch (err) {
        errorEl.textContent = "Submission failed — please try again.";
        console.error("Failed to submit mark:", err);
    }
});
