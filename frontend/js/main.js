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
        const response = await fetch(`${API_BASE_URL}/api/history`);
        if (!response.ok) throw new Error(`request failed: ${response.status}`);
        const history = await response.json();

        new Chart(document.getElementById("history-chart"), {
            type: "line",
            data: {
                labels: history.map((row) => row.year),
                datasets: [
                    {
                        label: "Actual cutoff",
                        data: history.map((row) => row.actual_cutoff),
                        borderColor: "#1f77b4",
                        backgroundColor: "#1f77b4",
                    },
                    {
                        label: "Safe grade",
                        data: history.map((row) => row.safe_grade),
                        borderColor: "#2ca02c",
                        backgroundColor: "#2ca02c",
                    },
                ],
            },
            options: {
                scales: { y: { title: { display: true, text: "Average (%)" } } },
            },
        });
    } catch (err) {
        console.error("Failed to load /api/history:", err);
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
