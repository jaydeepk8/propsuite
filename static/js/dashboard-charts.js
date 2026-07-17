/* ============================================================
   PropSuite dashboard charts (Chart.js)

   Shared by the owner and admin dashboards. Reads its data from
   {{ ...|json_script }} tags rendered by the template:
     #revLabels  #revValues  #occOccupied  #occVacant
   ============================================================ */

(function () {
  "use strict";

  const BRAND = "#2456e6";
  const TRACK = "#e3e8f7";

  /** Safely read a json_script payload; returns fallback if absent. */
  function readJSON(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return fallback;
    }
  }

  // ---- Revenue trends (area chart) ----
  const revCanvas = document.getElementById("revenueChart");
  if (revCanvas) {
    const gradient = revCanvas.getContext("2d").createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, "rgba(36, 86, 230, 0.28)");
    gradient.addColorStop(1, "rgba(36, 86, 230, 0.01)");

    new Chart(revCanvas, {
      type: "line",
      data: {
        labels: readJSON("revLabels", []),
        datasets: [{
          data: readJSON("revValues", []),
          borderColor: BRAND,
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: "#fff",
          pointBorderColor: BRAND,
          pointBorderWidth: 2,
          pointHoverRadius: 5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (c) => "₹" + c.parsed.y.toLocaleString() },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            border: { display: false },
            grid: { color: "#eef0f6" },
            ticks: { callback: (v) => "₹" + (v >= 1000 ? v / 1000 + "k" : v) },
          },
          x: { border: { display: false }, grid: { display: false } },
        },
      },
    });
  }

  // ---- Portfolio health (donut) ----
  const occCanvas = document.getElementById("occupancyChart");
  if (occCanvas) {
    const occupied = readJSON("occOccupied", 0);
    const vacant = readJSON("occVacant", 0);
    const hasUnits = occupied + vacant > 0;

    new Chart(occCanvas, {
      type: "doughnut",
      data: {
        labels: ["Occupied", "Vacant"],
        datasets: [{
          // Show a neutral ring when there are no units yet.
          data: hasUnits ? [occupied, vacant] : [0, 1],
          backgroundColor: [BRAND, TRACK],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "75%",
        plugins: { legend: { display: false }, tooltip: { enabled: hasUnits } },
      },
    });
  }
})();
