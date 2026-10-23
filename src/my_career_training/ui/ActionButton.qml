import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    property bool quiet: false
    property bool danger: false
    property real textScale: 1
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    implicitHeight: Math.max(44, contentItem.implicitHeight + 24)
    implicitWidth: contentItem.implicitWidth + 34
    leftPadding: 17; rightPadding: 17; topPadding: 12; bottomPadding: 12
    Accessible.name: text
    contentItem: Text {
        text: control.text
        font.family: "Segoe UI"
        font.pixelSize: 14 * control.textScale
        font.weight: control.primary ? Font.DemiBold : Font.Medium
        color: !control.enabled ? "#667280" : control.primary ? "#0b1720" : control.danger ? "#ffab9a" : "#e6edf5"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 9
        color: !control.enabled ? "#17212b" : control.down ? "#436b82" : control.primary ? (control.hovered ? "#a1d9f7" : "#87c9ed") : control.hovered ? "#263848" : control.quiet ? "transparent" : "#1e2c39"
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? "#f8b477" : control.primary ? "transparent" : "#334858"
        Rectangle { visible: control.activeFocus; anchors.fill: parent; anchors.margins: -3; color: "transparent"; radius: 12; border.width: 1; border.color: "#f8b477" }
    }
}
