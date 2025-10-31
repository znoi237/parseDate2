// === FILE: static/js/training_feature_importance.js ===
let fiChart = null;
let fiLastUpdate = 0;

async function fetchFeatureImportance() {
  try {
    const resp = await fetch("/api/training/active/logs?limit=200");
    const data = await resp.json();
    const rows = data.data || [];
    if (!rows.length) return;

    // ищем последнюю запись с "feature importance top"
    const fiRow = [...rows].reverse().find(r =>
      r.message && r.message.toLowerCase().includes("feature importance")
    );
    if (!fiRow || !fiRow.data || !fiRow.data.top) return;

    if (fiRow.id === fiLastUpdate) return;
    fiLastUpdate = fiRow.id;

    const features = fiRow.data.top;
    renderFeatureImportance(features);
  } catch (err) {
    console.warn("fetchFeatureImportance error", err);
  }
}

function renderFeatureImportance(features) {
  const ctx = document.getElementById("featureImportanceChart").getContext("2d");
  const labels = features.map(f => f[0]);
  const values = features.map(f => (f[1] * 100).toFixed(2));

  if (fiChart) {
    fiChart.destroy();
  }

  fiChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Влияние признака (%)",
          data: values,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: "Feature Importance (по весам LogisticRegression)",
        },
      },
      scales: {
        x: { ticks: { color: "#444" } },
        y: { beginAtZero: true, ticks: { color: "#444" } },
      },
    },
  });
}

// автообновление
setInterval(fetchFeatureImportance, 5000);
fetchFeatureImportance();
