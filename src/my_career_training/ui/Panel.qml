import QtQuick
import QtQuick.Layouts

Rectangle {
    id: panel
    default property alias content: body.data
    property int inset: 24
    color: "#141f2a"
    radius: 14
    border.color: "#293a49"
    implicitHeight: body.implicitHeight + inset * 2
    ColumnLayout { id: body; anchors.fill: parent; anchors.margins: panel.inset; spacing: 14 }
}
