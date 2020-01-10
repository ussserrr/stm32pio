import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import Qt.labs.platform 1.1

import ProjectListItem 1.0

ApplicationWindow {
    visible: true
    width: 740
    height: 480
    title: qsTr("PyQt5 love QML")
    color: "whitesmoke"

    GridLayout {
        id: mainGrid
        columns: 2
        rows: 2

        ListView {
            width: 200; height: 250
            model: projectsModel
            delegate: Item {
                id: projectListItem
                width: ListView.view.width
                height: 40
                Column {
                    Text { text: '<b>Name:</b> ' + display.name }
                    Text { text: '<b>State:</b> ' + display.state }
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        projectListItem.ListView.view.currentIndex = index;
                        view2.currentIndex = index
                    }
                }
            }
            highlight: Rectangle { color: "lightsteelblue"; radius: 5 }
            // focus: true
        }

        SwipeView {
            id: view2
            Repeater {
                model: projectsModel
                delegate: Column {
                    property ProjectListItem listItem: projectsModel.getProject(index)
                    Connections {
                        target: listItem
                        onLogAdded: {
                            log.append(message);
                        }
                    }
                    ButtonGroup {
                        buttons: row.children
                        onClicked: {
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                if (buttonsModel.get(i).name === button.text) {
                                    const b = buttonsModel.get(i);
                                    let args = [];
                                    if (b.args) {
                                        args = b.args.split(' ');
                                    }
                                    listItem.run(b.action, args);
                                    break;
                                }
                            }
                        }
                    }
                    Row {
                        id: row
                        Repeater {
                            model: ListModel {
                                id: buttonsModel
                                ListElement {
                                    name: 'Generate'
                                    action: 'generate_code'
                                }
                                ListElement {
                                    name: 'Initialize PlatformIO'
                                    action: 'pio_init'
                                }
                            }
                            delegate: Button {
                                text: name
                                //rotation: -90
                            }
                        }
                    }
                    Rectangle {
                        width: 500
                        height: 380
                        ScrollView {
                            anchors.fill: parent
                            TextArea {
                                width: 500
                                height: 380
                                Component.onCompleted: listItem.completed()
                                id: log
                            }
                        }
                    }
                    // Text {
                    //     text: '<b>Name:</b> ' + display.name
                    // }
                    // Button {
                    //     text: 'editor'
                    //     onClicked: {
                    //         for (var i = 0; i < buttonsModel.count; ++i) {
                    //             if (buttonsModel.get(i).action === 'pio_init') {
                    //                 buttonsModel.get(i).args = 'code';
                    //                 break;
                    //             }
                    //         }
                    //     }
                    // }
                }
            }
        }

        FolderDialog {
            id: folderDialog
            currentFolder: StandardPaths.standardLocations(StandardPaths.HomeLocation)[0]
            onAccepted: {
                projectsModel.addProject(folder);
            }
        }

        Button {
            text: 'Add'
            onClicked: {
                folderDialog.open()
            }
        }
    }

    onClosing: Qt.quit()

}
