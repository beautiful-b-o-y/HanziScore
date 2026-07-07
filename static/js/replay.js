(function () {
  var canvas = null;
  var context = null;
  var recordSelect = null;
  var playButton = null;
  var pauseButton = null;
  var resetButton = null;
  var speedInput = null;
  var speedValue = null;
  var replayStatus = null;
  var explanationButton = null;
  var explanationSource = null;
  var explanationText = null;
  var eventSummary = null;
  var strokeDetailGrid = null;
  var dataEventTable = null;
  var metricEls = {};
  var currentRecord = null;
  var currentTimeMs = 0;
  var animationFrame = null;
  var playbackStartedAt = 0;

  function updateStatus(message) {
    if (replayStatus) {
      replayStatus.textContent = message;
    }
  }

  function getSpeed() {
    return speedInput ? Number(speedInput.value) || 1 : 1;
  }

  function setControlsEnabled(enabled) {
    if (recordSelect) {
      recordSelect.disabled = !enabled || recordSelect.options.length === 0;
    }
    if (playButton) {
      playButton.disabled = !enabled;
    }
    if (pauseButton) {
      pauseButton.disabled = true;
    }
    if (resetButton) {
      resetButton.disabled = !enabled;
    }
    if (speedInput) {
      speedInput.disabled = !enabled;
    }
    if (explanationButton) {
      explanationButton.disabled = !enabled;
    }
  }

  function resetExplanation(message) {
    if (explanationSource) {
      explanationSource.textContent = "--";
    }
    if (explanationText) {
      explanationText.textContent = message || "Select a record to generate an explanation.";
    }
  }

  function drawGuide(width, height) {
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);

    context.strokeStyle = "#e2e8e5";
    context.lineWidth = 1;

    var cells = 4;
    for (var index = 1; index < cells; index += 1) {
      var x = (width / cells) * index;
      var y = (height / cells) * index;

      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();

      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }

    context.strokeStyle = "#d4dfda";
    context.setLineDash([8, 8]);

    context.beginPath();
    context.moveTo(0, 0);
    context.lineTo(width, height);
    context.stroke();

    context.beginPath();
    context.moveTo(width, 0);
    context.lineTo(0, height);
    context.stroke();

    context.setLineDash([]);

    context.strokeStyle = "#9d2f2f";
    context.lineWidth = 2;
    context.strokeRect(1, 1, width - 2, height - 2);
  }

  function fitCanvas() {
    var rect = canvas.getBoundingClientRect();
    var ratio = window.devicePixelRatio || 1;
    var width = Math.max(1, Math.floor(rect.width));
    var height = Math.max(1, Math.floor(rect.height));

    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawFrame(currentTimeMs);
  }

  function getPayload() {
    return currentRecord && currentRecord.sample ? currentRecord.sample.payload : null;
  }

  function getStrokes() {
    var payload = getPayload();
    return payload && Array.isArray(payload.strokes) ? payload.strokes : [];
  }

  function getMetrics() {
    return currentRecord && currentRecord.analysis ? currentRecord.analysis.metrics || {} : {};
  }

  function getTimelineStart() {
    var start = Infinity;
    getStrokes().forEach(function (stroke) {
      stroke.points.forEach(function (point) {
        start = Math.min(start, Number(point.t) || 0);
      });
    });
    return start === Infinity ? 0 : start;
  }

  function getDurationMs() {
    var metrics = getMetrics();
    if (Number.isFinite(metrics.durationMs) && metrics.durationMs > 0) {
      return metrics.durationMs;
    }

    var start = getTimelineStart();
    var end = start;
    getStrokes().forEach(function (stroke) {
      stroke.points.forEach(function (point) {
        end = Math.max(end, Number(point.t) || 0);
      });
    });
    return Math.max(0, end - start);
  }

  function transformPoint(point) {
    var rect = canvas.getBoundingClientRect();
    var payload = getPayload() || {};
    var sourceCanvas = payload.canvas || {};
    var sourceWidth = Number(sourceCanvas.width) || rect.width;
    var sourceHeight = Number(sourceCanvas.height) || rect.height;

    return {
      x: (Number(point.x) || 0) * (rect.width / sourceWidth),
      y: (Number(point.y) || 0) * (rect.height / sourceHeight),
      pressure: Number(point.pressure) || 0.5,
    };
  }

  function drawDot(point) {
    var transformed = transformPoint(point);
    context.fillStyle = "#1f2925";
    context.beginPath();
    context.arc(transformed.x, transformed.y, 1.8 + transformed.pressure, 0, Math.PI * 2);
    context.fill();
  }

  function drawSegment(previousPoint, nextPoint) {
    var previous = transformPoint(previousPoint);
    var next = transformPoint(nextPoint);
    context.strokeStyle = "#1f2925";
    context.lineWidth = 2.4 + next.pressure * 2.2;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(previous.x, previous.y);
    context.lineTo(next.x, next.y);
    context.stroke();
  }

  function drawFrame(elapsedMs) {
    if (!canvas || !context) {
      return;
    }

    var rect = canvas.getBoundingClientRect();
    var timelineStart = getTimelineStart();
    drawGuide(rect.width, rect.height);

    getStrokes().forEach(function (stroke) {
      var points = stroke.points || [];
      if (!points.length) {
        return;
      }

      var firstPointTime = (Number(points[0].t) || 0) - timelineStart;
      if (firstPointTime <= elapsedMs) {
        drawDot(points[0]);
      }

      for (var index = 1; index < points.length; index += 1) {
        var previous = points[index - 1];
        var current = points[index];
        var previousTime = (Number(previous.t) || 0) - timelineStart;
        var currentTime = (Number(current.t) || 0) - timelineStart;

        if (currentTime <= elapsedMs) {
          drawSegment(previous, current);
        } else if (previousTime <= elapsedMs && currentTime > previousTime) {
          var progress = (elapsedMs - previousTime) / (currentTime - previousTime);
          var partial = {
            x: Number(previous.x) + (Number(current.x) - Number(previous.x)) * progress,
            y: Number(previous.y) + (Number(current.y) - Number(previous.y)) * progress,
            pressure:
              Number(previous.pressure || 0.5) +
              (Number(current.pressure || 0.5) - Number(previous.pressure || 0.5)) * progress,
          };
          drawSegment(previous, partial);
          break;
        } else if (previousTime > elapsedMs) {
          break;
        }
      }
    });
  }

  function stopAnimation() {
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    if (playButton) {
      playButton.disabled = !currentRecord;
    }
    if (pauseButton) {
      pauseButton.disabled = true;
    }
  }

  function tick() {
    var durationMs = getDurationMs();
    currentTimeMs = (performance.now() - playbackStartedAt) * getSpeed();

    if (currentTimeMs >= durationMs) {
      currentTimeMs = durationMs;
      drawFrame(currentTimeMs);
      stopAnimation();
      updateStatus("Finished");
      return;
    }

    drawFrame(currentTimeMs);
    animationFrame = requestAnimationFrame(tick);
  }

  function play() {
    if (!currentRecord) {
      return;
    }

    var durationMs = getDurationMs();
    if (currentTimeMs >= durationMs) {
      currentTimeMs = 0;
    }

    playbackStartedAt = performance.now() - currentTimeMs / getSpeed();
    if (playButton) {
      playButton.disabled = true;
    }
    if (pauseButton) {
      pauseButton.disabled = false;
    }
    updateStatus("Playing");
    animationFrame = requestAnimationFrame(tick);
  }

  function pause() {
    stopAnimation();
    updateStatus("Paused");
  }

  function reset() {
    stopAnimation();
    currentTimeMs = 0;
    drawFrame(currentTimeMs);
    updateStatus(currentRecord ? "Ready" : "No record");
  }

  function updateMetrics() {
    var metrics = getMetrics();
    var targetCharacter =
      currentRecord && currentRecord.analysis ? currentRecord.analysis.targetCharacter || "--" : "--";

    metricEls.recordId.textContent = currentRecord ? currentRecord.id : "--";
    metricEls.target.textContent = targetCharacter || "--";
    metricEls.strokes.textContent = String(metrics.strokeCount ?? "--");
    metricEls.points.textContent = String(metrics.pointCount ?? "--");
    metricEls.duration.textContent = metrics.durationMs !== undefined ? metrics.durationMs + " ms" : "--";
    metricEls.path.textContent = metrics.pathLengthPx !== undefined ? metrics.pathLengthPx + " px" : "--";
    metricEls.speed.textContent =
      metrics.averageSpeedPxPerSecond !== undefined ? metrics.averageSpeedPxPerSecond + " px/s" : "--";
    metricEls.pauses.textContent = String(metrics.pauseCount ?? "--");
  }

  function formatNumber(value, suffix) {
    if (!Number.isFinite(Number(value))) {
      return "--";
    }
    return String(value) + (suffix || "");
  }

  function getAnalysisStrokes() {
    var analysis = currentRecord && currentRecord.analysis ? currentRecord.analysis : {};
    return Array.isArray(analysis.strokes) ? analysis.strokes : [];
  }

  function getDataEvents() {
    var analysis = currentRecord && currentRecord.analysis ? currentRecord.analysis : {};
    var summary = analysis.event_summary || {};
    return Array.isArray(summary.data_events) ? summary.data_events : [];
  }

  function clearChildren(element) {
    if (!element) {
      return;
    }
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  function appendMetric(parent, label, value) {
    var item = document.createElement("div");
    var title = document.createElement("dt");
    var detail = document.createElement("dd");
    title.textContent = label;
    detail.textContent = value;
    item.appendChild(title);
    item.appendChild(detail);
    parent.appendChild(item);
  }

  function renderStrokeEvents() {
    var strokes = getAnalysisStrokes();
    var events = getDataEvents();

    if (eventSummary) {
      eventSummary.textContent = currentRecord
        ? strokes.length + " stroke event record(s), " + events.length + " data event(s)."
        : "Select a saved record to view stroke-level events.";
    }

    clearChildren(strokeDetailGrid);
    clearChildren(dataEventTable);

    if (!currentRecord) {
      if (dataEventTable) {
        var emptyRow = document.createElement("tr");
        var emptyCell = document.createElement("td");
        emptyCell.colSpan = 4;
        emptyCell.textContent = "No record loaded.";
        emptyRow.appendChild(emptyCell);
        dataEventTable.appendChild(emptyRow);
      }
      return;
    }

    strokes.forEach(function (stroke) {
      var geometry = stroke.geometry || {};
      var dynamics = stroke.dynamics || {};
      var card = document.createElement("article");
      var heading = document.createElement("h3");
      var metrics = document.createElement("dl");
      var labelLine = document.createElement("p");
      var visualNote = document.createElement("p");
      var labels = Array.isArray(stroke.labels) ? stroke.labels : [];
      var turns = Array.isArray(geometry.turning_points) ? geometry.turning_points : [];

      card.className = "stroke-card";
      metrics.className = "stroke-card-metrics";
      labelLine.className = "stroke-labels";
      visualNote.className = "visual-note";

      heading.textContent = "Stroke " + stroke.index;
      appendMetric(metrics, "Mean speed", formatNumber(dynamics.mean_speed, " px/s"));
      appendMetric(metrics, "Max speed", formatNumber(dynamics.max_speed, " px/s"));
      appendMetric(metrics, "Pause before", formatNumber(dynamics.pause_before_ms, " ms"));
      appendMetric(metrics, "Pause after", formatNumber(dynamics.pause_after_ms, " ms"));
      appendMetric(metrics, "Turns", String(turns.length));
      appendMetric(metrics, "Path", formatNumber(geometry.path_length, " px"));

      labelLine.textContent = labels.length
        ? labels.map(function (label) { return label.type; }).join(", ")
        : "No data event labels crossed thresholds.";
      visualNote.textContent =
        stroke.visual_proxy && stroke.visual_proxy.width_profile_source
          ? "Width proxy: " + stroke.visual_proxy.width_profile_source
          : "Width proxy: unavailable";

      card.appendChild(heading);
      card.appendChild(metrics);
      card.appendChild(labelLine);
      card.appendChild(visualNote);
      strokeDetailGrid.appendChild(card);
    });

    if (!events.length && dataEventTable) {
      var noEventRow = document.createElement("tr");
      var noEventCell = document.createElement("td");
      noEventCell.colSpan = 4;
      noEventCell.textContent = "No data events crossed the configured thresholds.";
      noEventRow.appendChild(noEventCell);
      dataEventTable.appendChild(noEventRow);
      return;
    }

    events.forEach(function (event) {
      var row = document.createElement("tr");
      ["strokeIndex", "type", "value", "threshold"].forEach(function (key) {
        var cell = document.createElement("td");
        if (key === "value" || key === "threshold") {
          cell.textContent = String(event[key]) + (event.unit ? " " + event.unit : "");
        } else {
          cell.textContent = String(event[key] || "--");
        }
        row.appendChild(cell);
      });
      dataEventTable.appendChild(row);
    });
  }

  function formatRecordOption(record) {
    var target = record.targetCharacter ? " / " + record.targetCharacter : "";
    var strokes = record.strokeCount !== undefined ? " / " + record.strokeCount + " strokes" : "";
    return record.id + target + strokes;
  }

  async function loadRecord(recordId) {
    if (!recordId || !window.HanziScoreApi) {
      currentRecord = null;
      updateMetrics();
      renderStrokeEvents();
      setControlsEnabled(false);
      drawFrame(0);
      resetExplanation();
      updateStatus("No record");
      return;
    }

    updateStatus("Loading");
    stopAnimation();

    try {
      currentRecord = await window.HanziScoreApi.getRecord(recordId);
      currentTimeMs = 0;
      updateMetrics();
      renderStrokeEvents();
      setControlsEnabled(true);
      drawFrame(currentTimeMs);
      resetExplanation("Click Generate explanation to view the writing-process note.");
      updateStatus("Ready");
    } catch (error) {
      currentRecord = null;
      updateMetrics();
      renderStrokeEvents();
      setControlsEnabled(false);
      drawFrame(0);
      resetExplanation();
      updateStatus(error.message || "Load failed");
    }
  }

  async function loadExplanation() {
    if (!currentRecord || !window.HanziScoreApi || !window.HanziScoreApi.getExplanation) {
      return;
    }

    explanationButton.disabled = true;
    if (explanationSource) {
      explanationSource.textContent = "Generating";
    }
    if (explanationText) {
      explanationText.textContent = "Generating explanation...";
    }

    try {
      var result = await window.HanziScoreApi.getExplanation(currentRecord.id);
      var sourceLabel = result.sourceLabel || result.source || "--";
      if (result.cachedSourceLabel) {
        sourceLabel += " / Original source: " + result.cachedSourceLabel;
      }
      if (explanationSource) {
        explanationSource.textContent = sourceLabel;
      }
      if (explanationText) {
        var explanationBody = result.text || "No explanation available.";
        if (result.fallbackReason) {
          explanationBody += "\n\nZhipu fallback reason: " + result.fallbackReason;
        }
        explanationText.textContent = explanationBody;
      }
      updateStatus("Explanation ready");
    } catch (error) {
      if (explanationSource) {
        explanationSource.textContent = "--";
      }
      if (explanationText) {
        explanationText.textContent = error.message || "Explanation failed";
      }
      updateStatus(error.message || "Explanation failed");
    } finally {
      explanationButton.disabled = !currentRecord;
    }
  }

  async function refreshRecords(preferredId) {
    if (!window.HanziScoreApi || !recordSelect) {
      return;
    }

    try {
      var records = await window.HanziScoreApi.listRecords();
      recordSelect.innerHTML = "";

      if (!records.length) {
        var emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "No records";
        recordSelect.appendChild(emptyOption);
        currentRecord = null;
        updateMetrics();
        renderStrokeEvents();
        setControlsEnabled(false);
        drawFrame(0);
        resetExplanation();
        updateStatus("No records");
        return;
      }

      records.forEach(function (record) {
        var option = document.createElement("option");
        option.value = record.id;
        option.textContent = formatRecordOption(record);
        recordSelect.appendChild(option);
      });

      var nextId = preferredId || records[0].id;
      recordSelect.value = nextId;
      await loadRecord(nextId);
    } catch (error) {
      updateStatus(error.message || "Record list failed");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    canvas = document.getElementById("replay-canvas");
    if (!canvas) {
      return;
    }

    context = canvas.getContext("2d");
    recordSelect = document.getElementById("record-select");
    playButton = document.getElementById("replay-play");
    pauseButton = document.getElementById("replay-pause");
    resetButton = document.getElementById("replay-reset");
    speedInput = document.getElementById("replay-speed");
    speedValue = document.getElementById("replay-speed-value");
    replayStatus = document.getElementById("replay-status");
    explanationButton = document.getElementById("explanation-load");
    explanationSource = document.getElementById("explanation-source");
    explanationText = document.getElementById("explanation-text");
    eventSummary = document.getElementById("event-summary");
    strokeDetailGrid = document.getElementById("stroke-detail-grid");
    dataEventTable = document.getElementById("data-event-table");
    metricEls = {
      recordId: document.getElementById("replay-record-id"),
      target: document.getElementById("replay-target"),
      strokes: document.getElementById("replay-strokes"),
      points: document.getElementById("replay-points"),
      duration: document.getElementById("replay-duration"),
      path: document.getElementById("replay-path"),
      speed: document.getElementById("replay-speed-metric"),
      pauses: document.getElementById("replay-pauses"),
    };

    fitCanvas();
    setControlsEnabled(false);
    updateMetrics();
    renderStrokeEvents();
    resetExplanation();

    window.addEventListener("resize", fitCanvas);
    recordSelect.addEventListener("change", function () {
      loadRecord(recordSelect.value);
    });
    playButton.addEventListener("click", play);
    pauseButton.addEventListener("click", pause);
    resetButton.addEventListener("click", reset);
    if (explanationButton) {
      explanationButton.addEventListener("click", loadExplanation);
    }
    speedInput.addEventListener("input", function () {
      speedValue.textContent = getSpeed() + "x";
      if (animationFrame !== null) {
        playbackStartedAt = performance.now() - currentTimeMs / getSpeed();
      }
    });
    document.addEventListener("hanziscore:capture-saved", function (event) {
      var recordId = event.detail ? event.detail.recordId : "";
      refreshRecords(recordId);
    });

    refreshRecords();
  });
})();
