(function () {
  function drawGuide(canvas, context, width, height) {
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

  function fitCanvas(canvas) {
    var rect = canvas.getBoundingClientRect();
    var ratio = window.devicePixelRatio || 1;
    var width = Math.max(1, Math.floor(rect.width));
    var height = Math.max(1, Math.floor(rect.height));

    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);

    var context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawGuide(canvas, context, width, height);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var canvas = document.getElementById("writing-canvas");
    if (!canvas) {
      return;
    }

    fitCanvas(canvas);
    window.addEventListener("resize", function () {
      fitCanvas(canvas);
    });
  });
})();
