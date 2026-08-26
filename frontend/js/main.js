// Fetches predictions from the backend API and renders them.
const API_BASE_URL = "http://localhost:5000";

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

loadEstimate("/api/estimate", "cutoff-grade", "estimated_cutoff");
loadEstimate("/api/estimate/safe", "safe-grade", "estimated_safe_grade");

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

        new Chart(document.getElementById("history-chart"), {
            type: "line",
            data: {
                labels,
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
            },
            options: {
                scales: { y: { title: { display: true, text: "Average (%)" } } },
            },
        });
    } catch (err) {
        console.error("Failed to load history/estimate for chart:", err);
    }
}

async function loadBacktestTable() {
    const tbody = document.querySelector("#backtest-table tbody");
    const summaryEl = document.getElementById("backtest-summary");
    try {
        const response = await fetch(`${API_BASE_URL}/api/backtest`);
        if (!response.ok) throw new Error(`request failed: ${response.status}`);
        const { results, summary } = await response.json();

        tbody.innerHTML = "";
        for (const row of results) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${row.year}</td><td>${row.actual.toFixed(1)}</td>` +
                `<td>${row.predicted.toFixed(2)}</td><td>${row.error > 0 ? "+" : ""}${row.error.toFixed(2)}</td>`;
            tbody.appendChild(tr);
        }

        summaryEl.textContent = summary.n
            ? `n=${summary.n}, MAE=${summary.mae}, RMSE=${summary.rmse}, Bias=${summary.bias > 0 ? "+" : ""}${summary.bias}`
            : "Not enough resolved years yet to backtest.";
    } catch (err) {
        summaryEl.textContent = "Failed to load backtest results.";
        console.error("Failed to load /api/backtest:", err);
    }
}

loadHistoryChart();
loadBacktestTable();
