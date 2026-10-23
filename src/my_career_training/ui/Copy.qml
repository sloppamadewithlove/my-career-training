import QtQuick
import QtQuick.Controls

Label {
    property string tone: "body"
    property real scale: 1
    color: tone === "muted" ? "#9caebb" : tone === "accent" ? "#91d4f5" : "#e8f0f5"
    font.family: "Segoe UI"
    font.pixelSize: (tone === "hero" ? 42 : tone === "title" ? 27 : tone === "heading" ? 18 : tone === "small" ? 12 : 14) * scale
    font.weight: tone === "hero" || tone === "title" ? Font.DemiBold : tone === "heading" ? Font.Medium : Font.Normal
    wrapMode: Text.WordWrap
    lineHeight: 1.15
    textFormat: Text.PlainText
}
