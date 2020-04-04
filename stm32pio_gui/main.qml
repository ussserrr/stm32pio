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
    minimumWidth: 980  // comfortable initial size
    minimumHeight: 300
    height: 530
    title: 'stm32pio'
    color: 'whitesmoke'

    /*
       Notify the front-end about the end of an initial loading
    */
    signal backendLoaded()
    onBackendLoaded: loadingOverlay.close()
    Popup {
        id: loadingOverlay
        visible: true
        parent: Overlay.overlay
        anchors.centerIn: Overlay.overlay
        modal: true
        background: Rectangle { opacity: 0.0 }
        closePolicy: Popup.NoAutoClose

        contentItem: Column {
            BusyIndicator {}
            Text { text: 'Loading...' }
        }
    }

    /*
       Slightly customized QSettings
    */
    property Settings settings: appSettings
    QtDialogs.Dialog {
        id: settingsDialog
        title: 'Settings'
        standardButtons: QtDialogs.StandardButton.Save | QtDialogs.StandardButton.Cancel
        GridLayout {
            columns: 2

            Label {
                text: 'Editor'
                Layout.preferredWidth: 140
            }
            TextField {
                id: editor
            }

            Label {
                text: 'Verbose output'
                Layout.preferredWidth: 140
            }
            CheckBox {
                id: verbose
                leftPadding: -3
            }
        }
        // Set UI values there so they are always reflect actual parameters
        onVisibleChanged: {
            if (visible) {
                editor.text = settings.get('editor');
                verbose.checked = settings.get('verbose');
            }
        }
        onAccepted: {
            settings.set('editor', editor.text);
            settings.set('verbose', verbose.checked);
        }
    }

    QtDialogs.Dialog {
        id: aboutDialog
        title: 'About'
        standardButtons: QtDialogs.StandardButton.Close
        ColumnLayout {
            Rectangle {
                width: 250
                height: 100
                TextArea {
                    width: parent.width
                    height: parent.height
                    readOnly: true
                    selectByMouse: true
                    wrapMode: Text.WordWrap
                    textFormat: TextEdit.RichText
                    horizontalAlignment: TextEdit.AlignHCenter
                    verticalAlignment: TextEdit.AlignVCenter
                    text: `2018 - 2020 © ussserrr<br>
                           <a href='https://github.com/ussserrr/stm32pio'>GitHub</a>`
                    onLinkActivated: Qt.openUrlExternally(link)
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.NoButton  // we don't want to eat clicks on the Text
                        cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor
                    }
                }
            }
        }
    }

    /*
       The project visual representation is, in fact, split in two main parts: one in a list and one is
       an actual workspace. To avoid some possible bloopers we should make sure that both of them are loaded
       (at least at the subsistence level) before performing any actions with the project. To not reveal these
       QML-side implementation details to the backend we define this helper function that counts and stores
       a number of widgets currently loaded for each project in model and informs the Qt-side right after all
       necessary components become ready.
    */
    property var initInfo: ({})
    function setInitInfo(projectIndex) {
        if (projectIndex in initInfo) {
            initInfo[projectIndex]++;
        } else {
            initInfo[projectIndex] = 1;
        }

        if (initInfo[projectIndex] === 2) {
            delete initInfo[projectIndex];  // index can be reused
            projectsModel.getProject(projectIndex).qmlLoaded();
        }
    }

    // TODO: fix (jumps skipping next)
    function moveToNextAndRemove() {
        // Select and go to some adjacent index before deleting the current project. -1 is a correct
        // QML index (note that for Python it can jump to the end of the list, ensure a consistency!)
        const indexToRemove = projectsListView.currentIndex;
        let indexToMoveTo;
        if (indexToRemove === (projectsListView.count - 1)) {
            indexToMoveTo = indexToRemove - 1;
        } else {
            indexToMoveTo = indexToRemove + 1;
        }

        projectsListView.currentIndex = indexToMoveTo;
        projectsWorkspaceView.currentIndex = indexToMoveTo;

        // There is some strange bug when the workspace view (highest level StackLayout) disappears after
        // the project deletion (even when the removal is performed in a separated Timer after some delay
        // and the current index is definitely has already changed for both widgets)
        projectsModel.removeProject(indexToRemove);
    }

    menuBar: MenuBar {
        Menu {
            title: '&Menu'
            Action { text: '&Settings'; onTriggered: settingsDialog.open() }
            Action { text: '&About'; onTriggered: aboutDialog.open() }
            MenuSeparator { }
            // Use this instead of Qt.qiut() to prevent segfaults (messed up shutdown order)
            Action { text: '&Quit'; onTriggered: mainWindow.close() }
        }
    }

    DropArea {
        id: dropArea
        anchors.fill: parent
        Popup {
            visible: dropArea.containsDrag
            parent: Overlay.overlay
            anchors.centerIn: Overlay.overlay
            modal: true
            background: Rectangle { opacity: 0.0 }
            // closePolicy: Popup.NoAutoClose

            contentItem: Column {
                spacing: 20
                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: 'icons/drop-here.svg'
                    fillMode: Image.PreserveAspectFit
                    sourceSize.width: 64
                }
                Text {
                    // anchors.topMargin: 20
                    text: "Drop project folder to add..."
                }
            }
        }
        onDropped: {
            console.log(drop.urls, typeof(drop.urls), drop.text, drop.formats);
            if (drop.urls.length) {
                // typeof(drop.urls) === 'object' so we need to convert to the array of strings
                projectsModel.addProjectByPath(Object.keys(drop.urls).map(u => drop.urls[u]));
            } else if (drop.text) {
                // wrap into the array for consistency
                projectsModel.addProjectByPath([drop.text]);
            } else {
                console.log("Incorrect drag'n'drop event");
            }
        }
    }

    /*
       All layouts and widgets try to be adaptive to variable parents, siblings, window and whatever else sizes
       so we extensively use Grid, Column and Row layouts. The most high-level one is a composition of the list
       and the workspace in two columns
    */
    GridLayout {
        anchors.fill: parent
        rows: 1
        z: 2  // do not clip glow animation (see below)

        ColumnLayout {
            Layout.preferredWidth: 2.6 * parent.width / 12
            Layout.fillHeight: true

            /*
               The dynamic list of projects (initially loaded from the QSettings, can be modified later)
            */
            ListView {
                id: projectsListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true  // crawls under the Add/Remove buttons otherwise

                highlight: Rectangle { color: 'darkseagreen' }
                highlightMoveDuration: 0  // turn off animations
                highlightMoveVelocity: -1

                model: projectsModel  // backend-side
                delegate: Component {
                    /*
                       (See setInitInfo docs) One of the two main widgets representing the project. Use Loader component
                       as it can give us the relible time of all its children loading completion (unlike Component.onCompleted)
                    */
                    Loader {
                        onLoaded: setInitInfo(index)
                        sourceComponent: RowLayout {
                            property bool initLoading: true  // initial waiting for the backend-side
                            property ProjectListItem project: projectsModel.getProject(index)
                            Connections {
                                target: project  // (newbie hint) sender
                                // Currently, this event is equivalent to the complete initialization of the backend side of the project
                                onNameChanged: {
                                    initLoading = false;
                                }
                            }
                            ColumnLayout {
                                Layout.preferredHeight: 50

                                Text {
                                    leftPadding: 5
                                    rightPadding: busy.running ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.preferredWidth: busy.running ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideMiddle
                                    maximumLineCount: 1
                                    text: `<b>${display.name}</b>`
                                }
                                Text {
                                    leftPadding: 5
                                    rightPadding: busy.running ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignTop
                                    Layout.preferredWidth: busy.running ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                    text: display.current_stage
                                }
                            }

                            BusyIndicator {
                                id: busy
                                Layout.alignment: Qt.AlignVCenter
                                Layout.preferredWidth: parent.height
                                Layout.preferredHeight: parent.height
                                running: parent.initLoading || (project && project.actionRunning)
                            }

                            MouseArea {
                                x: parent.x
                                y: parent.y
                                width: parent.width
                                height: parent.height
                                enabled: !parent.initLoading
                                onClicked: {
                                    projectsListView.currentIndex = index;
                                    projectsWorkspaceView.currentIndex = index;
                                }
                            }
                        }
                    }
                }
            }

            QtLabs.FolderDialog {
                id: addProjectFolderDialog
                currentFolder: QtLabs.StandardPaths.standardLocations(QtLabs.StandardPaths.HomeLocation)[0]
                onAccepted: projectsModel.addProjectByPath(folder)
            }
            RowLayout {
                Layout.alignment: Qt.AlignBottom | Qt.AlignHCenter
                Layout.fillWidth: true

                Connections {
                    target: projectsModel
                    onDuplicateFound: {
                        projectsListView.currentIndex = duplicateIndex;
                        projectsWorkspaceView.currentIndex = duplicateIndex;
                    }
                }
                Button {
                    text: 'Add'
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    display: AbstractButton.TextBesideIcon
                    icon.source: 'icons/add.svg'
                    onClicked: addProjectFolderDialog.open()
                }
                Button {
                    text: 'Remove'
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    display: AbstractButton.TextBesideIcon
                    icon.source: 'icons/remove.svg'
                    onClicked: moveToNextAndRemove()
                }
            }
        }


        /*
           Main workspace. StackLayout's Repeater component seamlessly uses the same projects model (showing one -
           current - project per screen) as the list so all data is synchronized without any additional effort.
        */
        StackLayout {
            id: projectsWorkspaceView
            Layout.preferredWidth: 9.4 * parent.width / 12
            Layout.fillHeight: true
            Layout.leftMargin: 5
            Layout.rightMargin: 10
            Layout.topMargin: 10

            Repeater {
                // Use similar to ListView pattern (same projects model, Loader component)
                model: projectsModel
                delegate: Component {
                    Loader {
                        property int projectIndex: -1
                        onLoaded: {
                            projectIndex = index;
                            setInitInfo(projectIndex)
                        }
                        /*
                           Use another one StackLayout to separate Project initialization "screen" and Main one
                        */
                        sourceComponent: StackLayout {
                            id: mainOrInitScreen  // for clarity
                            currentIndex: -1  // at widget creation we do not show main nor init screen

                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            property ProjectListItem project: projectsModel.getProject(index)

                            Connections {
                                target: project  // sender
                                onLogAdded: {
                                    if (level === Logging.WARNING) {
                                        log.append('<font color="goldenrod"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                                    } else if (level >= Logging.ERROR) {
                                        log.append('<font color="red"><pre style="white-space: pre-wrap">' + message + '</pre></font>');
                                    } else {
                                        log.append('<pre style="white-space: pre-wrap">' + message + '</pre>');
                                    }
                                }
                                // Currently, this event is equivalent to the complete initialization of the backend side of the project
                                onNameChanged: {
                                    const state = project.state;
                                    const completedStages = Object.keys(state).filter(stateName => state[stateName]);
                                    if (completedStages.length === 1 && completedStages[0] === 'EMPTY') {
                                        initScreenLoader.active = true;
                                        mainOrInitScreen.currentIndex = 0;  // show init dialog
                                    } else {
                                        mainOrInitScreen.currentIndex = 1;  // show main view
                                    }
                                }
                            }

                            /*
                                Detect changes of a project outside of the app
                            */
                            QtDialogs.MessageDialog {
                                id: projectIncorrectDialog
                                text: `The project was modified outside of the stm32pio and .ioc file is no longer present.<br>
                                       The project will be removed from the app. It will not affect any real content`
                                icon: QtDialogs.StandardIcon.Critical
                                onAccepted: {
                                    moveToNextAndRemove();
                                    mainOrInitScreen.projectIncorrectDialogIsOpen = false;
                                }
                            }
                            signal handleState()
                            property bool projectIncorrectDialogIsOpen: false
                            property var stateCached: ({})
                            onHandleState: {
                                if (mainWindow.active && (projectIndex === projectsWorkspaceView.currentIndex) && !projectIncorrectDialogIsOpen && !project.actionRunning) {
                                    const state = project.state;
                                    stateCached = state;

                                    project.stageChanged();  // side-effect: get the stage at the same time

                                    if (!state['INIT_ERROR'] && !state['EMPTY']) {  // i.e. no .ioc file but the project was able to initialize itself
                                        // projectIncorrectDialog.visible is not working correctly (seems like delay or smth.)
                                        projectIncorrectDialogIsOpen = true;
                                        projectIncorrectDialog.open();
                                    }
                                }
                            }
                            Component.onCompleted: {
                                // Several events lead to a single handler
                                project.stateChanged.connect(handleState);
                                projectsWorkspaceView.currentIndexChanged.connect(handleState);  // the project was selected in the list
                                mainWindow.activeChanged.connect(handleState);  // the app window has got the focus
                            }


                            /*
                               Index: 0. Project initialization "screen"

                               Prompt a user to perform initial setup
                            */
                            Loader {
                                id: initScreenLoader
                                active: false
                                sourceComponent: Column {
                                    Text {
                                        text: "To complete initialization you can provide PlatformIO name of the board"
                                        padding: 10
                                    }
                                    Row {
                                        padding: 10
                                        spacing: 10
                                        ComboBox {
                                            id: board
                                            width: 200
                                            editable: true
                                            model: boardsModel  // backend-side (simple string model)
                                            textRole: 'display'
                                            onAccepted: {
                                                focus = false;
                                            }
                                            onActivated: {
                                                focus = false;
                                            }
                                            onFocusChanged: {
                                                if (!focus) {
                                                    if (find(editText) === -1) {
                                                        editText = textAt(0);  // should be 'None' at index 0
                                                    }
                                                } else {
                                                    selectAll();
                                                }
                                            }
                                        }
                                        /*
                                           Trigger full run
                                        */
                                        CheckBox {
                                            id: runCheckBox
                                            text: 'Run'
                                            enabled: false
                                            ToolTip {
                                                visible: runCheckBox.hovered
                                                Component.onCompleted: {
                                                    const actions = [];
                                                    for (let i = buttonsModel.statefulActionsStartIndex; i < buttonsModel.count; ++i) {
                                                        actions.push(`<b>${buttonsModel.get(i).name}</b>`);
                                                    }
                                                    text = `Do: ${actions.join(' → ')}`;
                                                }
                                            }
                                            Connections {
                                                target: board
                                                onFocusChanged: {
                                                    if (!board.focus) {
                                                        if (board.editText === board.textAt(0)) {  // should be 'None' at index 0
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
                                                text: "Start the editor specified in the <b>Settings</b> after the completion"
                                                visible: openEditor.hovered
                                            }
                                        }
                                    }
                                    Button {
                                        text: 'OK'
                                        topInset: 15
                                        leftInset: 10
                                        topPadding: 20
                                        leftPadding: 18
                                        onClicked: {
                                            // All 'run' operations will be queued
                                            project.run('save_config', [{
                                                'project': {
                                                    'board': board.editText === board.textAt(0) ? '' : board.editText
                                                }
                                            }]);
                                            if (board.editText === board.textAt(0)) {
                                                project.logAdded("WARNING  STM32 PlatformIO board is not specified, it will be needed on PlatformIO \
                                                                  project creation. You can set it in 'stm32pio.ini' file in the project directory",
                                                                 Logging.WARNING);
                                            }

                                            if (runCheckBox.checked) {
                                                for (let i = buttonsModel.statefulActionsStartIndex + 1; i < buttonsModel.count; ++i) {
                                                    project.run(buttonsModel.get(i).action, []);
                                                }
                                            }

                                            if (openEditor.checked) {
                                                project.run('start_editor', [settings.get('editor')]);
                                            }

                                            mainOrInitScreen.currentIndex = 1;  // go to main screen
                                            initScreenLoader.sourceComponent = undefined;  // destroy init screen
                                        }
                                    }
                                }
                            }

                            /*
                               Index: 1. Main "screen"
                            */
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                property var stateCachedNotifier: stateCached
                                onStateCachedNotifierChanged: {
                                    if (stateCached['INIT_ERROR']) {
                                        projActionsRow.visible = false;
                                        initErrorMessage.visible = true;
                                    }
                                }

                                /*
                                   Show this or action buttons
                                */
                                Text {
                                    id: initErrorMessage
                                    visible: false
                                    padding: 10
                                    text: "The project cannot be initialized"
                                    color: 'red'
                                }

                                /*
                                   The core widget - a group of buttons mapping all main actions that can be performed on the given project.
                                   They also serve the project state displaying - each button indicates a stage associated with it:
                                    - green: done
                                    - yellow: in progress right now
                                    - red: an error has occured during the last execution
                                */
                                RowLayout {
                                    id: projActionsRow
                                    Layout.fillWidth: true
                                    Layout.bottomMargin: 7
                                    z: 1  // for the glowing animation
                                    Connections {
                                        target: project
                                        onNameChanged: {
                                            for (let i = 0; i < buttonsModel.count; ++i) {
                                                // Looks like 'enabled' property should be managed from outside of the element
                                                // (i.e there, not in the button itself)
                                                projActionsRow.children[i].enabled = true;
                                            }
                                        }
                                        onActionStarted: {
                                            for (let i = 0; i < buttonsModel.count; ++i) {
                                                projActionsRow.children[i].enabled = false;
                                                projActionsRow.children[i].palette.buttonText = 'darkgray';
                                                projActionsRow.children[i].glowVisible = false;
                                            }
                                        }
                                        onActionDone: {
                                            for (let i = 0; i < buttonsModel.count; ++i) {
                                                projActionsRow.children[i].enabled = true;
                                                projActionsRow.children[i].palette.buttonText = 'black';
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: ListModel {
                                            id: buttonsModel
                                            readonly property int statefulActionsStartIndex: 2
                                            ListElement {
                                                name: 'Clean'
                                                action: 'clean'
                                                tooltip: "<b>WARNING:</b> this will delete <b>ALL</b> content of the project folder except the current .ioc file and clear all logs"
                                            }
                                            ListElement {
                                                name: 'Open editor'
                                                action: 'start_editor'
                                                margin: 15  // margin to visually separate first 2 actions as they doesn't represent any state
                                            }
                                            ListElement {
                                                name: 'Initialize'
                                                stateRepresented: 'INITIALIZED'  // the project state that this button is representing
                                                action: 'save_config'
                                            }
                                            ListElement {
                                                name: 'Generate'
                                                stateRepresented: 'GENERATED'
                                                action: 'generate_code'
                                            }
                                            ListElement {
                                                name: 'Init PlatformIO'
                                                stateRepresented: 'PIO_INITIALIZED'
                                                action: 'pio_init'
                                            }
                                            ListElement {
                                                name: 'Patch'
                                                stateRepresented: 'PATCHED'
                                                action: 'patch'
                                            }
                                            ListElement {
                                                name: 'Build'
                                                stateRepresented: 'BUILT'
                                                action: 'build'
                                            }
                                        }
                                        delegate: Button {
                                            text: model.name
                                            Layout.rightMargin: model.margin
                                            enabled: false  // turn on after project initialization
                                            property alias glowVisible: glow.visible
                                            property var stateCachedNotifier: stateCached
                                            onStateCachedNotifierChanged: {
                                                if (stateCached[model.stateRepresented]) {
                                                    palette.button = 'lightgreen';
                                                } else {
                                                    palette.button = 'lightgray';
                                                }
                                                palette.buttonText = 'black';
                                            }
                                            property int buttonIndex: -1
                                            Component.onCompleted: {
                                                buttonIndex = index;
                                            }
                                            onClicked: {
                                                const args = [];  // JS array cannot be attached to a ListElement (at least in a non-hacky manner)
                                                switch (model.action) {
                                                    case 'start_editor':
                                                        args.push(settings.get('editor'));
                                                        break;
                                                    case 'clean':
                                                        log.clear();
                                                        break;
                                                    default:
                                                        break;
                                                }
                                                project.run(model.action, args);
                                            }
                                            ToolTip {
                                                visible: parent.hovered
                                                Component.onCompleted: {
                                                    if (model.tooltip) {
                                                        text = model.tooltip;
                                                    } else {
                                                        this.destroy();
                                                    }
                                                }
                                            }
                                            property string currentColor: ''  // for highlighting only
                                            function highlight(flag) {
                                                if (flag) {
                                                    if (!currentColor) {
                                                        currentColor = palette.button;
                                                    }
                                                    palette.button = Qt.lighter('lightgreen', 1.2);
                                                    palette.buttonText = 'dimgray';
                                                } else {
                                                    palette.button = currentColor;
                                                    palette.buttonText = 'black';
                                                    currentColor = '';
                                                }
                                            }
                                            /*
                                               Detect modifier keys:
                                                - Ctrl (Cmd): start the editor after an operation(s)
                                                - Shift: continuous actions run
                                            */
                                            MouseArea {
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                property bool ctrlPressed: false
                                                property bool ctrlPressedLastState: false
                                                property bool shiftPressed: false
                                                property bool shiftPressedLastState: false
                                                function shiftHandler() {
                                                    for (let i = buttonsModel.statefulActionsStartIndex; i <= buttonIndex; ++i) {
                                                        projActionsRow.children[i].highlight(shiftPressed);
                                                    }
                                                }
                                                onClicked: {
                                                    if (shiftPressed && buttonIndex >= buttonsModel.statefulActionsStartIndex) {
                                                        for (let i = buttonsModel.statefulActionsStartIndex; i <= buttonIndex; ++i) {
                                                            projActionsRow.children[i].highlight(false);
                                                        }
                                                        for (let i = buttonsModel.statefulActionsStartIndex; i < buttonIndex; ++i) {
                                                            project.run(buttonsModel.get(i).action, []);
                                                        }
                                                    }
                                                    parent.clicked();
                                                    if (ctrlPressed && model.action !== 'start_editor') {
                                                        project.run('start_editor', [settings.get('editor')]);
                                                    }
                                                }
                                                onPositionChanged: {
                                                    ctrlPressed = mouse.modifiers & Qt.ControlModifier;  // bitwise AND
                                                    if (ctrlPressedLastState !== ctrlPressed) {
                                                        ctrlPressedLastState = ctrlPressed;
                                                    }

                                                    shiftPressed = mouse.modifiers & Qt.ShiftModifier;  // bitwise AND
                                                    if (shiftPressedLastState !== shiftPressed) {
                                                        shiftPressedLastState = shiftPressed;
                                                        shiftHandler();
                                                    }
                                                }
                                                onEntered: {
                                                    if (model.action !== 'start_editor') {
                                                        let preparedText =
                                                            `<b>Ctrl</b>-click to open the editor specified in the <b>Settings</b> after the operation`;
                                                        if (buttonIndex >= buttonsModel.statefulActionsStartIndex) {
                                                            preparedText +=
                                                                `, <b>Shift</b>-click to perform all actions prior this one (including).
                                                                 <b>Ctrl</b>-<b>Shift</b>-click for both`;
                                                        }
                                                        statusBar.text = preparedText;
                                                    }
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
                                                onPressed: {
                                                    palette.button = Qt.darker(palette.button, 1.2);
                                                }
                                                onReleased: {
                                                    palette.button = Qt.lighter(palette.button, 1.2);;
                                                }
                                            }
                                            Connections {
                                                target: project
                                                onActionStarted: {
                                                    if (action === model.action) {
                                                        palette.button = 'gold';
                                                    }
                                                }
                                                onActionDone: {
                                                    if (action === model.action) {
                                                        if (success) {
                                                            glow.color = 'lightgreen';
                                                        } else {
                                                            palette.button = 'lightcoral';
                                                            glow.color = 'lightcoral';
                                                        }
                                                        glow.visible = true;
                                                    }
                                                }
                                            }
                                            /*
                                               Blinky glowing
                                            */
                                            RectangularGlow {
                                                id: glow
                                                visible: false
                                                anchors.fill: parent
                                                cornerRadius: 25
                                                glowRadius: 20
                                                spread: 0.25
                                                onVisibleChanged: {
                                                    visible ? glowAnimation.start() : glowAnimation.complete();
                                                }
                                                SequentialAnimation {
                                                    id: glowAnimation
                                                    loops: 3
                                                    onStopped: {
                                                        glow.visible = false;
                                                    }
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
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true

                                    ScrollView {
                                        anchors.fill: parent
                                        TextArea {
                                            id: log
                                            readOnly: true
                                            selectByMouse: true
                                            wrapMode: Text.WordWrap
                                            font.family: 'Courier'
                                            font.pointSize: 10  // different on different platforms, Qt's bug
                                            textFormat: TextEdit.RichText
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    /*
       Simple text line. Currently, doesn't support smart intrinsic properties as a fully-fledged status bar,
       but is used only for a single feature so not a big deal
    */
    footer: Text {
        id: statusBar
        padding: 10
    }
}
