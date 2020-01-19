import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtQuick.Dialogs 1.3 as QtDialogs
import Qt.labs.platform 1.1 as QtLabs

import ProjectListItem 1.0


ApplicationWindow {
    id: mainWindow
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
            id: listView
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
                        listView.currentIndex = index;
                        swipeView.currentIndex = index;
                    }
                }
            }
            highlight: Rectangle { color: "lightsteelblue"; radius: 5 }
            // focus: true
        }

        SwipeView {
            id: swipeView
            clip: true
            Repeater {
                model: projectsModel
                delegate: Column {
                    property ProjectListItem listItem: projectsModel.getProject(index)
                    Connections {
                        target: listItem  // sender
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
                        // onStateChanged: {
                        //     for (let i = 0; i < buttonsModel.count; ++i) {
                        //         // row.children[i].palette.button = 'lightcoral';
                        //         // buttonsModel.get(i).stateChangedHandler();
                        //     }
                        // }
                    }
                    QtDialogs.MessageDialog {
                        id: projectIncorrectDialog
                        text: "The project was modified outside of the stm32pio and .ioc file is no longer present. " +
                              "The project will be removed from the app. It will not affect any real content"
                        icon: QtDialogs.StandardIcon.Critical
                        onAccepted: {
                            console.log('on accepted');
                            const delIndex = swipeView.currentIndex;
                            listView.currentIndex = swipeView.currentIndex + 1;
                            swipeView.currentIndex = swipeView.currentIndex + 1;
                            projectsModel.removeProject(delIndex);
                            buttonGroup.lock = false;
                        }
                    }
                    ButtonGroup {
                        id: buttonGroup
                        buttons: row.children
                        signal stateReceived()
                        signal actionResult(string action, bool success)
                        property bool lock: false
                        onStateReceived: {
                            if (active && index == swipeView.currentIndex && !lock) {
                                console.log('onStateReceived', index);

                                const state = projectsModel.getProject(swipeView.currentIndex).state;
                                listItem.stageChanged();

                                if (!state['EMPTY']) {
                                    lock = true;  // projectIncorrectDialog.visible is not working correctly (seems like delay or smth.)
                                    projectIncorrectDialog.open();
                                    console.log('no .ioc file');
                                } else if (state['EMPTY']) {
                                    // delete state['UNDEFINED'];
                                    // delete state['EMPTY'];
                                    Object.keys(state).forEach(key => {
                                        for (let i = 0; i < buttonsModel.count; ++i) {
                                            if (buttonsModel.get(i).state === key) {
                                                if (state[key]) {
                                                    row.children[i].palette.button = 'lightgreen';
                                                } else {
                                                    row.children[i].palette.button = 'lightgray';
                                                }
                                                break;
                                            }
                                        }
                                    });
                                }
                            }
                        }
                        onActionResult: {
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                if (buttonsModel.get(i).action === action) {
                                    if (success === false) {
                                        // TODO: change to fade animation. Also, can blink a log area in the same way
                                        row.children[i].palette.button = 'lightcoral';
                                    }
                                    break;
                                }
                            }
                        }
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
                        Component.onCompleted: {
                            listItem.stateChanged.connect(stateReceived);
                            swipeView.currentItemChanged.connect(stateReceived);
                            mainWindow.activeChanged.connect(stateReceived);

                            listItem.actionResult.connect(actionResult);
                        }
                    }
                    Row {
                        id: row
                        Repeater {
                            model: ListModel {
                                id: buttonsModel
                                ListElement {
                                    name: 'Initialize'
                                    state: 'INITIALIZED'
                                    action: 'save_config'
                                }
                                ListElement {
                                    name: 'Generate'
                                    state: 'GENERATED'
                                    action: 'generate_code'
                                }
                                ListElement {
                                    name: 'Initialize PlatformIO'
                                    state: 'PIO_INITIALIZED'
                                    action: 'pio_init'
                                }
                                ListElement {
                                    name: 'Patch'
                                    state: 'PATCHED'
                                    action: 'patch'
                                }
                                ListElement {
                                    name: 'Build'
                                    state: 'BUILT'
                                    action: 'build'
                                }
                            }
                            delegate: Button {
                                text: name
                                // rotation: -90
                            }
                        }
                    }
                    Rectangle {
                        width: 500
                        height: 380
                        ScrollView {
                            anchors.fill: parent
                            TextArea {
                                id: log
                                width: 500
                                height: 380
                                readOnly: true
                                selectByMouse: true
                                wrapMode: Text.WordWrap
                                font.family: 'Courier'
                                Component.onCompleted: listItem.completed()
                            }
                        }
                    }
                    // Text {
                    //     text: '<b>Name:</b> ' + display.name
                    // }
                    // Button {
                    //     text: 'editor'
                    //     onClicked: {
                    //         projectIncorrectDialog.open();
                    //     }
                    // }
                }
            }
        }

        QtLabs.FolderDialog {
            id: folderDialog
            currentFolder: QtLabs.StandardPaths.standardLocations(QtLabs.StandardPaths.HomeLocation)[0]
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

    // onClosing: Qt.quit()
    onActiveChanged: {
        if (active) {
            console.log('window received focus', swipeView.currentIndex);
        }
    }

}
