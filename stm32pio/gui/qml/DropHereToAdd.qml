import QtQuick 2.14
import QtQuick.Controls 2.14


DropArea {
    id: dropArea
    anchors.fill: parent
    Popup {
        visible: dropArea.containsDrag
        parent: Overlay.overlay
        anchors.centerIn: Overlay.overlay
        modal: true
        background: Rectangle { opacity: 0.0 }
        Overlay.modal: Rectangle { color: "#aaffffff" }
        contentItem: Column {
            spacing: 20
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: '../icons/drop-here.svg'
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 64
            }
            Text {
                text: "Drop projects here to add..."
                font.pointSize: 24  // different on different platforms, Qt's bug
                font.weight: Font.Black  // heaviest
            }
        }
    }
    onDropped: {
        if (drop.urls.length) {
            // We need to convert to an array of strings since typeof(drop.urls) === 'object'
            projectsModel.addProjectsByPaths(Object.values(drop.urls));
        } else if (drop.text) {
            // Wrap into an array for consistency
            projectsModel.addProjectsByPaths([drop.text]);
        } else {
            console.warn("Incorrect drag'n'drop event");
        }
    }
}
