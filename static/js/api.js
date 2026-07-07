(function () {
  async function health() {
    const response = await fetch("/health", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Health check failed");
    }

    return response.json();
  }

  async function submitCapture(payload) {
    const response = await fetch("/api/captures", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Capture submit failed");
    }

    return result;
  }

  async function listRecords() {
    const response = await fetch("/api/records", {
      headers: {
        Accept: "application/json",
      },
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Record list failed");
    }

    return result.records || [];
  }

  async function getRecord(recordId) {
    const response = await fetch("/api/records/" + encodeURIComponent(recordId), {
      headers: {
        Accept: "application/json",
      },
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Record load failed");
    }

    return result;
  }

  async function getExplanation(recordId) {
    const response = await fetch("/api/records/" + encodeURIComponent(recordId) + "/explanation", {
      headers: {
        Accept: "application/json",
      },
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Explanation load failed");
    }

    return result;
  }

  window.HanziScoreApi = {
    health,
    submitCapture,
    listRecords,
    getRecord,
    getExplanation,
  };

  document.addEventListener("DOMContentLoaded", async function () {
    const status = document.getElementById("app-status");
    if (!status) {
      return;
    }

    try {
      const result = await health();
      status.textContent = result.status === "ok" ? "Ready" : "Unavailable";
      status.classList.add(result.status === "ok" ? "is-ok" : "is-error");
    } catch (error) {
      status.textContent = "Offline";
      status.classList.add("is-error");
    }
  });
})();
