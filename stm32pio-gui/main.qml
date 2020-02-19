import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtGraphicalEffects 1.12
import QtQuick.Dialogs 1.3 as QtDialogs
import Qt.labs.platform 1.1 as QtLabs

import ProjectListItem 1.0
import Settings 1.0


ApplicationWindow {
    id: mainWindow
    visible: true
    minimumWidth: 980
    minimumHeight: 300
    height: 530
    title: 'stm32pio'
    color: 'whitesmoke'

    GridLayout {
        anchors.fill: parent
        rows: 1

        ColumnLayout {
            Layout.preferredWidth: 2.5 * parent.width / 12
            Layout.fillHeight: true

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true

                highlight: Rectangle { color: 'darkseagreen' }
                highlightMoveDuration: 0
                highlightMoveVelocity: -1
                currentIndex: 0

                model: ListModel {
                    ListElement {
                        name: '<b>‎⁨MacSSD⁩ ▸ ⁨Пользователи⁩ ▸ ⁨chufyrev⁩ ▸ ⁨Документы⁩ ▸ ⁨STM32⁩ ▸ ⁨stm32cubemx</b>⁩'
                        state: 'Bla Bla Bla'
                        busy: false
                    }
                    ListElement {
                        name: '<b>exec java -jar /opt/stm32cubemx/STM32CubeMX.exe "$@"</b>⁩'
                        state: 'Abracadabra'
                        busy: true
                    }
                }
                delegate: RowLayout {
                    ColumnLayout {
                        Layout.preferredHeight: 50
                        Layout.leftMargin: 5
                        Layout.rightMargin: 5
                        Text {
                            Layout.alignment: Qt.AlignBottom
                            Layout.preferredWidth: model.busy ? list.width - parent.height : list.width
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            text: model.name
                        }
                        Text {
                            Layout.alignment: Qt.AlignTop
                            Layout.preferredWidth: model.busy ? list.width - parent.height : list.width
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            text: model.state
                        }
                    }

                    BusyIndicator {
                        visible: model.busy
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                        Layout.preferredWidth: parent.height
                        Layout.preferredHeight: parent.height
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignBottom | Qt.AlignHCenter

                Button {
                    text: 'Add'
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                }
                Button {
                    text: 'Remove'
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                }
            }
        }


        StackLayout {
            // Screen per project
            Layout.preferredWidth: 9.5 * parent.width / 12
            Layout.fillHeight: true
            Layout.margins: 10

            StackLayout {
                // Init screen or Work screen
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    RowLayout {
                        id: row
                        Layout.fillWidth: true
                        Layout.bottomMargin: 7
                        z: 1
                        Repeater {
                            model: ListModel {
                                id: buttonsModel
                                ListElement {
                                    name: 'Clean'
                                    action: 'clean'
                                    shouldStartEditor: false
                                }
                                ListElement {
                                    name: 'Open editor'
                                    action: 'start_editor'
                                    margin: 15  // margin to visually separate actions as they doesn't represent any state
                                }
                                ListElement {
                                    name: 'Initialize'
                                    state: 'INITIALIZED'
                                    action: 'save_config'
                                    shouldRunNext: false
                                    shouldStartEditor: false
                                }
                                ListElement {
                                    name: 'Generate'
                                    state: 'GENERATED'
                                    action: 'generate_code'
                                    shouldRunNext: false
                                    shouldStartEditor: false
                                }
                                ListElement {
                                    name: 'Init PlatformIO'
                                    state: 'PIO_INITIALIZED'
                                    action: 'pio_init'
                                    shouldRunNext: false
                                    shouldStartEditor: false
                                }
                                ListElement {
                                    name: 'Patch'
                                    state: 'PATCHED'
                                    action: 'patch'
                                    shouldRunNext: false
                                    shouldStartEditor: false
                                }
                                ListElement {
                                    name: 'Build'
                                    state: 'BUILT'
                                    action: 'build'
                                    shouldRunNext: false
                                    shouldStartEditor: false
                                }
                            }
                            delegate: Button {
                                text: name
                                Layout.rightMargin: model.margin
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.rightMargin: 2

                        ScrollView {
                            anchors.fill: parent
                            TextArea {
                                id: log
                                anchors.fill: parent
                                readOnly: true
                                selectByMouse: true
                                wrapMode: Text.WordWrap
                                font.family: 'Courier'
                                font.pointSize: 10
                                textFormat: TextEdit.RichText
                                text: 'AAA BBB'
                            }
                        }
                    }
                }
            }
        }
    }
}
