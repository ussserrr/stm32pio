import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import Qt.labs.platform 1.1

import ProjectListItem 1.0

ApplicationWindow {
    visible: true
    width: 740
    height: 480
    title: "stm32pio"
    color: "whitesmoke"

    GridLayout {
        id: mainGrid
        columns: 2
        rows: 2

        ListView {
            width: 200; height: 250
            model: projectsModel
            clip: true
            delegate: Item {
                id: projectListItem
                width: ListView.view.width
                height: 40
                Column {
                    Text { text: '<b>Name:</b> ' + display.name }
                    Text { text: '<b>State:</b> ' + display.current_stage }
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
            clip: true
            Repeater {
                model: projectsModel
                delegate: Column {
                    property ProjectListItem listItem: projectsModel.getProject(index)
                    Connections {
                        target: listItem
                        onLogAdded: {
                            log.append(message);
                        }
                        // Component.onCompleted: {
                        //     for (let i = 0; i < buttonsModel.count; ++i) {
                        //         // row.children[i].enabled = false;
                        //         // buttonsModel.get(i).stateChangedHandler();
                        //         listItem.stateChanged.connect(row.children[i].haha);
                        //     }
                        // }
                        onStateChanged: {
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                row.children[i].enabled = false;
                                // buttonsModel.get(i).stateChangedHandler();
                            }
                        }
                    }
                    ButtonGroup {
                        buttons: row.children
                        onClicked: {
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                if (buttonsModel.get(i).name === button.text) {
                                    const b = buttonsModel.get(i);
                                    const args = b.args ? b.args.split(' ') : [];
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
                                    name: 'Initialize'
                                    action: 'save_config'
                                }
                                ListElement {
                                    name: 'Generate'
                                    action: 'generate_code'
                                }
                                ListElement {
                                    name: 'Initialize PlatformIO'
                                    action: 'pio_init'
                                }
                                ListElement {
                                    name: 'Patch'
                                    action: 'patch'
                                }
                                ListElement {
                                    name: 'Build'
                                    action: 'build'
                                }
                            }
                            delegate: Button {
                                text: name
                                // rotation: -90
                                // Component.onCompleted: {
                                //     console.log(name);
                                // }
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
                                wrapMode: Text.WordWrap
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
