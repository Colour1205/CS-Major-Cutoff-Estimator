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
