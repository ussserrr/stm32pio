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
    width: 1130
    height: 550
    title: 'stm32pio'
    color: 'whitesmoke'

    property var initInfo: ({})
    function setInitInfo(projectIndex) {
        if (projectIndex in initInfo) {
            initInfo[projectIndex]++;
        } else {
            initInfo[projectIndex] = 1;
        }

        if (initInfo[projectIndex] === 2) {
            delete initInfo[projectIndex];  // index can be reused
            projectsModel.getProject(projectIndex).completed();
            const indexToOpen = listView.indexToOpenAfterAddition;
            console.log('indexToOpen', indexToOpen);
            if (indexToOpen !== -1) {
                listView.indexToOpenAfterAddition = -1;
                listView.currentIndex = indexToOpen;
                swipeView.currentIndex = indexToOpen;
            }
        }
        // Object.keys(initInfo).forEach(key => console.log('index:', key, 'counter:', initInfo[key]));
    }

    // property var indexChangeInfo: ({})
    // function setIndexChangeInfo(projectIndex) {
    //     if (projectIndex in indexChangeInfo) {
    //         indexChangeInfo[projectIndex]++;
    //     } else {
    //         indexChangeInfo[projectIndex] = 1;
    //     }

    //     if (indexChangeInfo[projectIndex] === 2) {
    //         delete indexChangeInfo[projectIndex];  // index can be reused
    //         const indexToRemove = listView.indexToRemoveAfterChangingCurrentIndex;
    //         if (indexToRemove !== -1) {
    //             console.log('should remove', indexToRemove, 'based on changing to', projectIndex);
    //             listView.indexToRemoveAfterChangingCurrentIndex = -1;
    //             projectsModel.removeProject(indexToRemove);
    //         }
    //     }
    // }

    GridLayout {
        id: mainGrid
        columns: 2
        rows: 2

        Column {
            ListView {
                id: listView
                width: 250
                height: 250
                model: projectsModel
                clip: true
                property int indexToOpenAfterAddition: -1
                // property int indexToRemoveAfterChangingCurrentIndex: -1
                highlight: Rectangle { color: 'lightsteelblue'; radius: 5 }
                highlightMoveDuration: 0
                highlightMoveVelocity: -1
                // focus: true
                delegate: Component {
                    Loader {
                        onLoaded: {
                            setInitInfo(index);
                        }
                        sourceComponent: Item {
                            id: iii
                            property bool loading: true
                            property bool actionRunning: false
                            width: listView.width
                            height: 40
                            property ProjectListItem listItem: projectsModel.getProject(index)
                            Connections {
                                target: listItem  // sender
                                onNameChanged: {
                                    loading = false;
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
                                enabled: !parent.loading
                                onClicked: {
                                    listView.currentIndex = index;
                                    swipeView.currentIndex = index;
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
                    listView.indexToOpenAfterAddition = listView.count;
                    projectsModel.addProject(folder);
                }
            }
            Row {
                padding: 10
                spacing: 10
                Button {
                    text: 'Add'
                    display: AbstractButton.TextBesideIcon
                    icon.source: 'icons/add.svg'
                    onClicked: {
                        folderDialog.open();
                    }
                }
                Button {
                    id: removeButton
                    text: 'Remove'
                    display: AbstractButton.TextBesideIcon
                    icon.source: 'icons/remove.svg'
                    onClicked: {
                        let indexToRemove = listView.currentIndex;
                        let indexToMove;
                        if (indexToRemove === (listView.count - 1)) {
                            if (listView.count === 1) {
                                indexToMove = -1;
                            } else {
                                indexToMove = indexToRemove - 1;
                            }
                        } else {
                            indexToMove = indexToRemove + 1;
                        }
                        console.log('indexToMove', indexToMove, 'indexToRemove', indexToRemove);
                        // listView.indexToRemoveAfterChangingCurrentIndex = indexToRemove;

                        // let cnt = 0;
                        // function bnbn() {
                        //     cnt++;
                        //     if (cnt === 2) {
                        //         function MyTimer() {
                        //             return Qt.createQmlObject("import QtQuick 2.0; Timer {}", removeButton);
                        //         }

                        //         const t = new MyTimer();
                        //         t.interval = 1000;
                        //         t.repeat = false;
                        //         t.triggered.connect(function () {
                        //             projectsModel.removeProject(indexToRemove);
                        //             // console.log('after remove', listView.currentIndex);
                        //             // projectsModel.getProject(listView.currentIndex).stateChanged();
                        //         })

                        //         t.start();

                        //         const t2 = new MyTimer();
                        //         t2.interval = 2000;
                        //         t2.repeat = false;
                        //         t2.triggered.connect(function () {
                        //             // projectsModel.removeProject(indexToRemove);
                        //             console.log('after remove', listView.currentIndex);
                        //             projectsModel.getProject(listView.currentIndex).stateChanged();
                        //         })

                        //         t2.start();
                        //     }
                        // }
                        // listView.currentIndexChanged.connect(bnbn);
                        // swipeView.currentIndexChanged.connect(bnbn);

                        listView.currentIndex = indexToMove;
                        swipeView.currentIndex = indexToMove;
                        projectsModel.removeProject(indexToRemove);
                    }
                }
            }
        }

        SwipeView {
            id: swipeView
            clip: true
            interactive: false
            orientation: Qt.Vertical
            Repeater {
                model: projectsModel
                delegate: Component {
                    Loader {
                        // active: SwipeView.isCurrentItem
                        onLoaded: {
                            setInitInfo(index);
                        }
                        sourceComponent: Column {
                            property ProjectListItem listItem: projectsModel.getProject(index)
                            Connections {
                                target: listItem  // sender
                                onLogAdded: {
                                    if (level === Logging.WARNING) {
                                        log.append('<font color="goldenrod"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                                    } else if (level >= Logging.ERROR) {
                                        log.append('<font color="red"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                                    } else {
                                        log.append('<pre style="white-space: pre-wrap">' + message + '</pre>');
                                    }
                                }
                                onNameChanged: {
                                    for (let i = 0; i < buttonsModel.count; ++i) {
                                        row.children[i].enabled = true;
                                    }

                                    const state = listItem.state;
                                    const s = Object.keys(state).filter(stateName => state[stateName]);
                                    if (s.length === 1 && s[0] === 'EMPTY') {
                                        initDialogLoader.active = true;
                                    } else {
                                        content.visible = true;
                                    }
                                }
                            }
                            Column {
                                id: content
                                visible: false
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
                                            // console.log('onStateReceived', active, index, !lock);
                                            const state = listItem.state;
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
                                                for (let i = 0; i < buttonsModel.count; ++i) {
                                                    row.children[i].palette.button = 'lightgray';
                                                    if (state[buttonsModel.get(i).state]) {
                                                        row.children[i].palette.button = 'lightgreen';
                                                    }
                                                }
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
                                RowLayout {
                                    id: row
                                    // padding: 10
                                    // spacing: 10
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
                                                args: 'code'
                                                margin: 15  // margin to visually separate the Clean action as it doesn't represent any state
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
                                                name: 'Initialize PlatformIO'
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
                                            enabled: false
                                            property alias glowingVisible: glow.visible
                                            property alias anim: seq
                                            Layout.margins: 10  // insets can be used too
                                            Layout.rightMargin: margin
                                            // rotation: -90
                                            function runOwnAction() {
                                                listView.currentItem.item.actionRunning = true;
                                                palette.button = 'gold';
                                                const args = model.args ? model.args.split(' ') : [];
                                                listItem.run(model.action, args);
                                            }
                                            onClicked: {
                                                runOwnAction();
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                property bool ctrlPressed: false
                                                property bool ctrlPressedLastState: false
                                                property bool shiftPressed: false
                                                property bool shiftPressedLastState: false
                                                // function h() {
                                                //     console.log('Show "Start the editor after operation" message');  // not for a 'Open editor' button
                                                // }
                                                function shiftHandler() {
                                                    // console.log('shiftHandler', shiftPressed, index);
                                                    for (let i = 2; i <= index; ++i) {  // TODO: magic number, actually...
                                                        if (shiftPressed) {
                                                            // if (Qt.colorEqual(row.children[i].palette.button, 'lightgray')) {
                                                                row.children[i].palette.button = 'honeydew';
                                                            // }
                                                        } else {
                                                            buttonGroup.stateReceived();
                                                            // if (Qt.colorEqual(row.children[i].palette.button, 'honeydew')) {
                                                            //     row.children[i].palette.button = 'lightgray';
                                                            // }
                                                        }
                                                    }
                                                }
                                                onClicked: {
                                                    if (ctrlPressed && model.action !== 'start_editor') {
                                                        model.shouldStartEditor = true;
                                                    }
                                                    if (shiftPressed && index >= 2) {
                                                        // run all actions in series
                                                        for (let i = 2; i < index; ++i) {
                                                            buttonsModel.setProperty(i, 'shouldRunNext', true);
                                                        }
                                                        row.children[2].clicked();
                                                        return;
                                                    }
                                                    parent.clicked();  // propagateComposedEvents doesn't work...
                                                }
                                                onPositionChanged: {
                                                    if (mouse.modifiers & Qt.ControlModifier) {
                                                        ctrlPressed = true;
                                                    } else {
                                                        ctrlPressed = false;
                                                    }
                                                    if (ctrlPressedLastState !== ctrlPressed) {
                                                        ctrlPressedLastState = ctrlPressed;
                                                    }

                                                    if (mouse.modifiers & Qt.ShiftModifier) {
                                                        shiftPressed = true;
                                                    } else {
                                                        shiftPressed = false;
                                                    }
                                                    if (shiftPressedLastState !== shiftPressed) {
                                                        shiftPressedLastState = shiftPressed;
                                                        shiftHandler();
                                                    }
                                                }
                                                onEntered: {
                                                    statusBar.text = '<b>Ctrl</b>-click to open the editor specified in the <b>Settings</b> after the operation, <b>Shift</b>-click to perform all actions prior this one (including). <b>Ctrl</b>-<b>Shift</b>-click for both';
                                                }
                                                onExited: {
                                                    statusBar.text = '';

                                                    ctrlPressed = false;
                                                    ctrlPressedLastState = false;

                                                    if (shiftPressed || shiftPressedLastState) {
                                                        shiftPressed = false;
                                                        shiftPressedLastState = false;
                                                        shiftHandler();
                                                    }
                                                }
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

                                                        if (model.shouldRunNext) {
                                                            model.shouldRunNext = false;
                                                            row.children[index + 1].clicked();  // complete task
                                                        }

                                                        if (model.shouldStartEditor) {
                                                            model.shouldStartEditor = false;
                                                            for (let i = 0; i < buttonsModel.count; ++i) {
                                                                if (buttonsModel.get(i).action === 'start_editor') {
                                                                    row.children[i].runOwnAction();  // no additional actions in outer handlers
                                                                    break;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            RectangularGlow {
                                                id: glow
                                                visible: false
                                                anchors.fill: parent
                                                cornerRadius: 25
                                                glowRadius: 20
                                                spread: 0.25
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
                                    width: 800
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
                                            font.pointSize: 10
                                            textFormat: TextEdit.RichText
                                            // Component.onCompleted: console.log('textArea completed');
                                        }
                                    }
                                }
                            }
                            Loader {
                                id: initDialogLoader
                                active: false
                                sourceComponent: Column {
                                    Text {
                                        text: 'To complete initialization you can provide PlatformIO name of the board'
                                    }
                                    Row {
                                        ComboBox {
                                            id: board
                                            editable: true
                                            model: ListModel {
                                                ListElement { text: "None" }
                                                ListElement { text: "Banana" }
                                                ListElement { text: "Apple" }
                                                ListElement { text: "Coconut" }
                                                ListElement { text: "nucleo_f031k6" }
                                            }
                                            onAccepted: {
                                                focus = false;
                                            }
                                            onActivated: {
                                                focus = false;
                                            }
                                            onFocusChanged: {
                                                if (!focus) {
                                                    if (find(editText) === -1) {
                                                        editText = textAt(0);
                                                    }
                                                }
                                            }
                                        }
                                        CheckBox {
                                            id: runCheckBox
                                            text: 'Run'
                                            enabled: false
                                            ToolTip {
                                                visible: runCheckBox.hovered
                                                delay: 250
                                                enter: Transition {
                                                    NumberAnimation { property: 'opacity'; from: 0.0; to: 1.0 }
                                                }
                                                exit: Transition {
                                                    NumberAnimation { property: 'opacity'; from: 1.0; to: 0.0 }
                                                }
                                                Component.onCompleted: {
                                                    const actions = [];
                                                    for (let i = 3; i < buttonsModel.count; ++i) {
                                                        actions.push(`<b>${buttonsModel.get(i).name}</b>`);
                                                    }
                                                    text = `Do: ${actions.join(' → ')}`;
                                                }
                                            }
                                            Connections {
                                                target: board
                                                onFocusChanged: {
                                                    if (!board.focus) {
                                                        if (board.editText === board.textAt(0)) {
                                                            runCheckBox.checked = false;
                                                            runCheckBox.enabled = false;
                                                        } else {
                                                            runCheckBox.enabled = true;
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        CheckBox {
                                            id: openEditor
                                            text: 'Open editor'
                                            ToolTip {
                                                text: 'Start the editor specified in the <b>Settings</b> after the completion'
                                                visible: openEditor.hovered
                                                delay: 250
                                                enter: Transition {
                                                    NumberAnimation { property: 'opacity'; from: 0.0; to: 1.0 }
                                                }
                                                exit: Transition {
                                                    NumberAnimation { property: 'opacity'; from: 1.0; to: 0.0 }
                                                }
                                            }
                                        }
                                    }
                                    Button {
                                        text: 'OK'
                                        onClicked: {
                                            listView.currentItem.item.actionRunning = true;

                                            listItem.run('save_config', [{
                                                'project': {
                                                    'board': board.editText === board.textAt(0) ? '' : board.editText
                                                }
                                            }]);

                                            if (runCheckBox.checked) {
                                                for (let i = 3; i < buttonsModel.count - 1; ++i) {
                                                    buttonsModel.setProperty(i, 'shouldRunNext', true);
                                                }
                                                row.children[3].clicked();
                                            }

                                            if (openEditor.checked) {
                                                if (runCheckBox.checked) {
                                                    buttonsModel.setProperty(buttonsModel.count - 1, 'shouldStartEditor', true);
                                                } else {
                                                    row.children[1].clicked();
                                                }
                                            }

                                            initDialogLoader.sourceComponent = undefined;
                                            content.visible = true;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            id: statusBar
            padding: 10
            Layout.columnSpan: 2
            // text: 'Status bar'
        }
    }


    // onClosing: Qt.quit()
    // onActiveChanged: {
    //     if (active) {
    //         console.log('window received focus', swipeView.currentIndex);
    //     }
    // }

}
