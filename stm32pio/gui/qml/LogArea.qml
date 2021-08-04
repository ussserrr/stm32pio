import QtQuick 2.14
import QtQuick.Controls 2.14


Rectangle {
    function clear() {
        log.clear();
    }
    ScrollView {
        anchors.fill: parent
        TextArea {
            id: log
            readOnly: true
            selectByMouse: true
            wrapMode: Text.WordWrap
            font.pointSize: 10  // different on different platforms, Qt's bug
            font.weight: Font.DemiBold
            textFormat: TextEdit.RichText
            Connections {
                target: project
                function onLogAdded(message, level) {
                    if (level === Logging.WARNING) {
                        log.append('<font color="goldenrod"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                    } else if (level >= Logging.ERROR) {
                        log.append('<font color="indianred"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                    } else {
                        log.append('<pre style="white-space: pre-wrap">' + message + '</pre>');
                    }
                }
            }
        }
    }
}
