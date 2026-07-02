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

  window.HanziScoreApi = {
    health,
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
