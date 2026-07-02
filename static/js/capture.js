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
  var strokeCount = null;
  var pointCount = null;
  var pointerTypes = null;
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

  function drawDot(point) {
    var pressure = point.pressure || 0.5;
    context.fillStyle = "#1f2925";
    context.beginPath();
    context.arc(point.x, point.y, 1.8 + pressure, 0, Math.PI * 2);
    context.fill();
  }

  function drawSegment(previousPoint, nextPoint) {
    var pressure = nextPoint.pressure || 0.5;
    context.strokeStyle = "#1f2925";
    context.lineWidth = 2.4 + pressure * 2.2;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(previousPoint.x, previousPoint.y);
    context.lineTo(nextPoint.x, nextPoint.y);
    context.stroke();
  }

  function drawStroke(points) {
    if (!points.length) {
      return;
    }

    drawDot(points[0]);
    for (var index = 1; index < points.length; index += 1) {
      drawSegment(points[index - 1], points[index]);
    }
  }

  function redraw() {
    if (!canvas || !context) {
      return;
    }

    var rect = canvas.getBoundingClientRect();
    drawGuide(rect.width, rect.height);

    strokes.forEach(function (stroke) {
      drawStroke(stroke.points);
    });

    if (activeStroke) {
      drawStroke(activeStroke.points);
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
        drawSegment(previousPoint, point);
      } else {
        drawDot(point);
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
      pointerTypes.textContent = types.length ? types.join(", ") : "未开始";
    }
    if (clearButton) {
      clearButton.disabled = visibleStrokes.length === 0;
    }
    if (saveButton) {
      saveButton.disabled = strokes.length === 0 || Boolean(activeStroke);
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
      updateStatus(
        "Received " + result.strokeCount + " strokes / " + result.pointCount + " points"
      );
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
    strokeCount = document.getElementById("stroke-count");
    pointCount = document.getElementById("point-count");
    pointerTypes = document.getElementById("pointer-types");
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

    updateCounters();
  });
})();
