(function () {
  var strokes = [];
  var activeStroke = null;
  var activePointerId = null;
  var captureStartMs = null;
  var canvas = null;
  var context = null;
  var clearButton = null;
  var saveButton = null;
  var targetInput = null;
  var brushSizeInput = null;
  var brushSizeValue = null;
  var strokeCount = null;
  var pointCount = null;
  var pointerTypes = null;
  var durationValue = null;
  var pathLengthValue = null;
  var speedValue = null;
  var pauseCountValue = null;
  var recordIdValue = null;
  var captureStatus = null;

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

    canvas.dataset.ready = "true";
  }

  function getBrushSize(stroke) {
    if (stroke && Number.isFinite(Number(stroke.brushSize))) {
      return Number(stroke.brushSize);
    }
    if (brushSizeInput) {
      return Number(brushSizeInput.value) || 7;
    }
    return 7;
  }

  function drawDot(point, stroke) {
    var pressure = point.pressure || 0.5;
    var brushSize = getBrushSize(stroke);
    context.fillStyle = "#1f2925";
    context.beginPath();
    context.arc(point.x, point.y, Math.max(2, brushSize * 0.45 + pressure), 0, Math.PI * 2);
    context.fill();
  }

  function drawSegment(previousPoint, nextPoint, stroke) {
    var pressure = nextPoint.pressure || 0.5;
    var brushSize = getBrushSize(stroke);
    context.strokeStyle = "#1f2925";
    context.lineWidth = brushSize + pressure * 1.2;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(previousPoint.x, previousPoint.y);
    context.lineTo(nextPoint.x, nextPoint.y);
    context.stroke();
  }

  function drawStroke(stroke) {
    var points = stroke.points || [];
    if (!points.length) {
      return;
    }

    drawDot(points[0], stroke);
    for (var index = 1; index < points.length; index += 1) {
      drawSegment(points[index - 1], points[index], stroke);
    }
  }

  function redraw() {
    if (!canvas || !context) {
      return;
    }

    var rect = canvas.getBoundingClientRect();
    drawGuide(rect.width, rect.height);

    strokes.forEach(function (stroke) {
      drawStroke(stroke);
    });

    if (activeStroke) {
      drawStroke(activeStroke);
    }
  }

  function fitCanvas() {
    var rect = canvas.getBoundingClientRect();
    var ratio = window.devicePixelRatio || 1;
    var width = Math.max(1, Math.floor(rect.width));
    var height = Math.max(1, Math.floor(rect.height));

    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    redraw();
  }

  function getEventPoint(event) {
    var rect = canvas.getBoundingClientRect();
    var pressure = Number.isFinite(event.pressure) ? event.pressure : 0;

    if (pressure === 0 && event.buttons) {
      pressure = 0.5;
    }

    return {
      x: Math.round((event.clientX - rect.left) * 100) / 100,
      y: Math.round((event.clientY - rect.top) * 100) / 100,
      t: Math.round(performance.now() - captureStartMs),
      pressure: Math.round(pressure * 1000) / 1000,
    };
  }

  function addPoint(event) {
    if (!activeStroke) {
      return;
    }

    var events = event.getCoalescedEvents ? event.getCoalescedEvents() : [event];
    events.forEach(function (sourceEvent) {
      var point = getEventPoint(sourceEvent);
      var points = activeStroke.points;
      var previousPoint = points[points.length - 1];

      points.push(point);
      if (previousPoint) {
        drawSegment(previousPoint, point, activeStroke);
      } else {
        drawDot(point, activeStroke);
      }
    });
  }

  function updateStatus(message) {
    if (captureStatus) {
      captureStatus.textContent = message;
    }
  }

  function updateCounters() {
    var visibleStrokes = activeStroke ? strokes.concat([activeStroke]) : strokes;
    var totalPoints = visibleStrokes.reduce(function (sum, stroke) {
      return sum + stroke.points.length;
    }, 0);
    var types = visibleStrokes
      .map(function (stroke) {
        return stroke.pointerType || "unknown";
      })
      .filter(function (value, index, list) {
        return list.indexOf(value) === index;
      });

    if (strokeCount) {
      strokeCount.textContent = String(visibleStrokes.length);
    }
    if (pointCount) {
      pointCount.textContent = String(totalPoints);
    }
    if (pointerTypes) {
      pointerTypes.textContent = types.length ? types.join(", ") : "Not started";
    }
    if (clearButton) {
      clearButton.disabled = visibleStrokes.length === 0;
    }
    if (saveButton) {
      saveButton.disabled = strokes.length === 0 || Boolean(activeStroke);
    }
  }

  function resetMetrics() {
    if (durationValue) {
      durationValue.textContent = "--";
    }
    if (pathLengthValue) {
      pathLengthValue.textContent = "--";
    }
    if (speedValue) {
      speedValue.textContent = "--";
    }
    if (pauseCountValue) {
      pauseCountValue.textContent = "--";
    }
    if (recordIdValue) {
      recordIdValue.textContent = "--";
    }
  }

  function showMetrics(result) {
    var metrics = result.metrics || {};

    if (durationValue) {
      durationValue.textContent = String(metrics.durationMs || 0) + " ms";
    }
    if (pathLengthValue) {
      pathLengthValue.textContent = String(metrics.pathLengthPx || 0) + " px";
    }
    if (speedValue) {
      speedValue.textContent = String(metrics.averageSpeedPxPerSecond || 0) + " px/s";
    }
    if (pauseCountValue) {
      pauseCountValue.textContent = String(metrics.pauseCount || 0);
    }
    if (recordIdValue) {
      recordIdValue.textContent = result.recordId || "--";
    }
  }

  function beginStroke(event) {
    event.preventDefault();

    if (activeStroke) {
      return;
    }

    if (captureStartMs === null) {
      captureStartMs = performance.now();
    }

    activePointerId = event.pointerId;
    activeStroke = {
      id: "stroke-" + String(strokes.length + 1),
      pointerType: event.pointerType || "unknown",
      brushSize: getBrushSize(),
      points: [],
    };

    canvas.setPointerCapture(activePointerId);
    addPoint(event);
    updateCounters();
    updateStatus("Recording");
  }

  function continueStroke(event) {
    if (!activeStroke || event.pointerId !== activePointerId) {
      return;
    }

    event.preventDefault();
    addPoint(event);
    updateCounters();
  }

  function finishStroke(event) {
    if (!activeStroke || event.pointerId !== activePointerId) {
      return;
    }

    event.preventDefault();
    addPoint(event);

    if (activeStroke.points.length > 0) {
      strokes.push(activeStroke);
    }

    if (canvas.hasPointerCapture(activePointerId)) {
      canvas.releasePointerCapture(activePointerId);
    }

    activeStroke = null;
    activePointerId = null;
    updateCounters();
    updateStatus("Ready");
  }

  function cancelStroke() {
    activeStroke = null;
    activePointerId = null;
    redraw();
    updateCounters();
    updateStatus("Ready");
  }

  function clearCapture() {
    strokes = [];
    activeStroke = null;
    activePointerId = null;
    captureStartMs = null;
    redraw();
    updateCounters();
    resetMetrics();
    updateStatus("Cleared");
  }

  function buildPayload() {
    var rect = canvas.getBoundingClientRect();
    return {
      version: 1,
      targetCharacter: targetInput ? targetInput.value.trim() : "",
      createdAt: new Date().toISOString(),
      canvas: {
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        devicePixelRatio: window.devicePixelRatio || 1,
      },
      input: {
        userAgent: window.navigator.userAgent,
        pointerTypes: strokes
          .map(function (stroke) {
            return stroke.pointerType || "unknown";
          })
          .filter(function (value, index, list) {
            return list.indexOf(value) === index;
          }),
      },
      strokes: strokes.map(function (stroke) {
        return {
          id: stroke.id,
          pointerType: stroke.pointerType,
          brushSize: stroke.brushSize,
          points: stroke.points.map(function (point) {
            return {
              x: point.x,
              y: point.y,
              t: point.t,
              pressure: point.pressure,
            };
          }),
        };
      }),
    };
  }

  async function saveCapture() {
    if (!window.HanziScoreApi || !window.HanziScoreApi.submitCapture) {
      updateStatus("API unavailable");
      return;
    }

    saveButton.disabled = true;
    updateStatus("Saving");

    try {
      var result = await window.HanziScoreApi.submitCapture(buildPayload());
      showMetrics(result);
      document.dispatchEvent(
        new CustomEvent("hanziscore:capture-saved", {
          detail: {
            recordId: result.recordId,
          },
        })
      );
      updateStatus("Saved " + result.recordId);
    } catch (error) {
      updateStatus(error.message || "Save failed");
    } finally {
      updateCounters();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    canvas = document.getElementById("writing-canvas");
    if (!canvas) {
      return;
    }

    context = canvas.getContext("2d");
    clearButton = document.getElementById("clear-canvas");
    saveButton = document.getElementById("save-capture");
    targetInput = document.getElementById("target-character");
    brushSizeInput = document.getElementById("brush-size");
    brushSizeValue = document.getElementById("brush-size-value");
    strokeCount = document.getElementById("stroke-count");
    pointCount = document.getElementById("point-count");
    pointerTypes = document.getElementById("pointer-types");
    durationValue = document.getElementById("duration-value");
    pathLengthValue = document.getElementById("path-length-value");
    speedValue = document.getElementById("speed-value");
    pauseCountValue = document.getElementById("pause-count-value");
    recordIdValue = document.getElementById("record-id-value");
    captureStatus = document.getElementById("capture-status");

    fitCanvas();
    window.addEventListener("resize", fitCanvas);

    canvas.addEventListener("pointerdown", beginStroke);
    canvas.addEventListener("pointermove", continueStroke);
    canvas.addEventListener("pointerup", finishStroke);
    canvas.addEventListener("pointercancel", cancelStroke);
    canvas.addEventListener("lostpointercapture", cancelStroke);

    if (clearButton) {
      clearButton.addEventListener("click", clearCapture);
    }
    if (saveButton) {
      saveButton.addEventListener("click", saveCapture);
    }
    if (brushSizeInput && brushSizeValue) {
      brushSizeInput.addEventListener("input", function () {
        brushSizeValue.textContent = brushSizeInput.value + " px";
      });
      brushSizeValue.textContent = brushSizeInput.value + " px";
    }

    updateCounters();
    resetMetrics();
  });
})();
