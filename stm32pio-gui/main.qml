import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtGraphicalEffects 1.12
import QtQuick.Dialogs 1.3 as QtDialogs
import Qt.labs.platform 1.1 as QtLabs

import ProjectListItem 1.0


ApplicationWindow {
    id: mainWindow
    visible: true
    width: 830
    height: 480
    title: "stm32pio"
    color: "whitesmoke"

    // Popup {
    //     id: popup
    //     anchors.centerIn: parent
    //     modal: true

    //     parent: Overlay.overlay
    //     background: Rectangle {
    //         color: '#00000000'
    //     }
    //     contentItem: Column {
    //         BusyIndicator {}
    //         Text { text: 'Loading...' }
    //     }
    // }

    GridLayout {
        id: mainGrid
        columns: 2
        rows: 2

        ListView {
            id: listView
            width: 250; height: 250
            model: projectsModel
            clip: true
            delegate: Item {
                id: iii
                property bool loading: true
                property bool actionRunning: false
                width: ListView.view.width
                height: 40
                property ProjectListItem listItem: projectsModel.getProject(index)
                Connections {
                    target: listItem  // sender
                    onNameChanged: {
                        loading = false;
                        // TODO: open the dialog where the user can enter board, editor etc.
                    }
                    onActionResult: {
                        actionRunning = false;
                    }
                }
                Row {
                    Column {
                        Text { text: '<b>Name:</b> ' + display.name }
                        Text { text: '<b>Stage:</b> ' + display.current_stage }
                    }
                    BusyIndicator {
                        running: iii.loading || iii.actionRunning
                        width: iii.height
                        height: iii.height
                    }
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
            interactive: false
            orientation: Qt.Vertical
            Repeater {
                model: projectsModel
                delegate: Column {
                    property ProjectListItem listItem: projectsModel.getProject(index)
                    Connections {
                        target: listItem  // sender
                        onLogAdded: {
                            log.append(message);
                        }
                        onNameChanged: {
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                row.children[i].enabled = true;
                            }
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
                        signal actionResult(string actionDone, bool success)
                        property bool lock: false
                        onStateReceived: {
                            if (active && index == swipeView.currentIndex && !lock) {
                                console.log('onStateReceived', active, index, !lock);

                                const state = projectsModel.getProject(swipeView.currentIndex).state;
                                listItem.stageChanged();

                                if (state['LOADING']) {
                                    // listView.currentItem.running = true;
                                } else if (state['INIT_ERROR']) {
                                    // listView.currentItem.running = false;
                                    row.visible = false;
                                    initErrorMessage.visible = true;
                                } else if (!state['EMPTY']) {
                                    lock = true;  // projectIncorrectDialog.visible is not working correctly (seems like delay or smth.)
                                    projectIncorrectDialog.open();
                                    console.log('no .ioc file');
                                } else if (state['EMPTY']) {
                                    // listView.currentItem.running = false;
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
                            // stopActionButton.visible = false;
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                row.children[i].enabled = true;
                            }
                        }
                        onClicked: {
                            // stopActionButton.visible = true;
                            // listView.currentItem.actionRunning = true;
                            for (let i = 0; i < buttonsModel.count; ++i) {
                                row.children[i].enabled = false;
                                row.children[i].glowingVisible = false;
                                row.children[i].anim.complete();
                                // if (buttonsModel.get(i).name === button.text) {
                                //     const b = buttonsModel.get(i);
                                //     const args = b.args ? b.args.split(' ') : [];
                                //     listItem.run(b.action, args);
                                // }
                            }
                        }
                        Component.onCompleted: {
                            listItem.stateChanged.connect(stateReceived);
                            swipeView.currentItemChanged.connect(stateReceived);
                            mainWindow.activeChanged.connect(stateReceived);

                            listItem.actionResult.connect(actionResult);
                        }
                    }
                    Text {
                        id: initErrorMessage
                        visible: false
                        padding: 10
                        text: "The project cannot be initialized"
                        color: 'red'
                    }
                    Row {
                        id: row
                        padding: 10
                        spacing: 10
                        z: 1
                        Repeater {
                            model: ListModel {
                                id: buttonsModel
                                // ListElement {
                                //     // TODO: add margin or divider or smth to visually separate the Clean action as it doesn't represent any state
                                //     name: 'Clean'
                                //     // state: 'INITIALIZED'
                                //     action: 'clean'
                                // }
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
                                id: actionButton
                                text: name
                                enabled: false
                                property alias glowingVisible: glow.visible
                                property alias anim: seq
                                // rotation: -90
                                onClicked: {
                                    listView.currentItem.actionRunning = true;
                                    const args = model.args ? model.args.split(' ') : [];
                                    listItem.run(model.action, args);
                                }
                                Connections {
                                    target: buttonGroup
                                    onActionResult: {
                                        // console.log('actionDone', actionDone, model.name);
                                        if (actionDone === model.action) {
                                            if (success) {
                                                glow.color = 'lightgreen';
                                            } else {
                                                palette.button = 'lightcoral';
                                                glow.color = 'lightcoral';
                                            }
                                            glow.visible = true;
                                            seq.start();
                                        }
                                    }
                                }
                                Glow {
                                    id: glow
                                    visible: false
                                    anchors.fill: actionButton
                                    radius: 10
                                    samples: 21
                                    color: 'lightgreen'
                                    source: actionButton
                                }
                                SequentialAnimation {
                                    id: seq
                                    loops: 3
                                    OpacityAnimator {
                                        target: glow
                                        from: 0
                                        to: 1
                                        duration: 1000
                                    }
                                    OpacityAnimator {
                                        target: glow
                                        from: 1
                                        to: 0
                                        duration: 1000
                                    }
                                }
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
                                // anchors.fill: parent
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
                    //     text: 'test'
                    //     onClicked: {
                    //         row.visible = false;
                    //     }
                    // }
                    // Button {
                    //     id: stopActionButton
                    //     text: 'Stop'
                    //     visible: false
                    //     palette.button: 'lightcoral'
                    //     onClicked: {
                    //         // projectIncorrectDialog.open();
                    //         console.log(listItem.stop('generate_code'));
                    //     }
                    // }
                    Column {
                        id: initDialog
                        // visible: false
                        Text {
                            text: 'You can specify blabla'
                        }
                        Row {
                            TextField {
                                placeholderText: 'Board'
                            }
                            TextField {
                                placeholderText: 'Editor'
                            }
                            CheckBox {
                                text: 'Build'
                                enabled: false
                            }
                        }
                    }
                }
            }
        }

        QtLabs.FolderDialog {
            id: folderDialog
            currentFolder: QtLabs.StandardPaths.standardLocations(QtLabs.StandardPaths.HomeLocation)[0]
            onAccepted: {
                // popup.open();
                projectsModel.addProject(folder);

                // listView.currentIndex = listView.count;
                // swipeView.currentIndex = listView.count;
            }
        }
        Button {
            text: 'Add'
            onClicked: {
                folderDialog.open();
            }
        }
    }

    // onClosing: Qt.quit()
    // onActiveChanged: {
    //     if (active) {
    //         console.log('window received focus', swipeView.currentIndex);
    //     }
    // }

}
