import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQuick.Layouts 1.14
import QtQuick.Dialogs 1.3 as Dialogs


Dialogs.Dialog {
    title: 'About'
    standardButtons: Dialogs.StandardButton.Close
    ColumnLayout {
        Rectangle {
            width: 280
            height: aboutDialogTextArea.implicitHeight
            TextArea {
                id: aboutDialogTextArea
                width: parent.width
                readOnly: true
                selectByMouse: true
                wrapMode: Text.WordWrap
                textFormat: TextEdit.RichText
                horizontalAlignment: TextEdit.AlignHCenter
                verticalAlignment: TextEdit.AlignVCenter
                text: `v${appVersion}<br>
                       2018 - 2021 © ussserrr<br>
                       <a href='https://github.com/ussserrr/stm32pio'>GitHub</a><br><br>

                       Powered by <b>Python</b>, <b>Qt</b>, <b>FlatIcons</b> and other awesome technologies.<br><br>

                       Please refer to supplied <a href='file://${rootPath}/LICENSE'>LICENSE</a> file for more
                       information. This software should be distributed alongside with its license`
                onLinkActivated: {
                    Qt.openUrlExternally(link);
                    aboutDialog.close();
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton  // we don't want to eat clicks on the Text
                    cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor
                }
            }
        }
    }
}
