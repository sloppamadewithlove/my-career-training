import QtQuick

Item {
    id: art
    opacity: 0.9
    Canvas {
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset();
            var w = width, h = height;
            c.save(); c.translate(w * 0.53, h * 0.49); c.rotate(-0.39);
            var rs = [0.31, 0.42, 0.53];
            for (var i = 0; i < rs.length; i++) {
                c.beginPath(); c.ellipse(-w * rs[i], -h * rs[i] * 0.64, w * rs[i] * 2, h * rs[i] * 1.28);
                c.strokeStyle = i === 1 ? "#5e9bbb" : "#294556"; c.lineWidth = i === 1 ? 3 : 1; c.stroke();
            }
            c.beginPath(); c.arc(w * 0.40, 0, 7, 0, Math.PI * 2); c.fillStyle = "#f2a669"; c.fill();
            c.beginPath(); c.moveTo(-42, 19); c.lineTo(-11, -25); c.lineTo(37, -25); c.lineTo(7, 19); c.closePath(); c.fillStyle = "#87c9ed"; c.fill();
            c.beginPath(); c.moveTo(-10, 30); c.lineTo(21, -14); c.lineTo(41, -14); c.lineTo(11, 30); c.closePath(); c.fillStyle = "#e2eef5"; c.fill();
            c.restore();
        }
    }
}
