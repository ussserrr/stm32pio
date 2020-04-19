import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtGraphicalEffects 1.12
import QtQuick.Dialogs 1.3 as Dialogs
import QtQml.StateMachine 1.12 as DSM

import Qt.labs.platform 1.1 as Labs

import ProjectListItem 1.0
import Settings 1.0


ApplicationWindow {
    id: mainWindow
    visible: true
    minimumWidth: 980  // comfortable initial size for all platforms (as the same style is used for any of them)
    minimumHeight: 300
    height: 530
    title: 'stm32pio'
    color: 'whitesmoke'

    /*
       Notify the front about the end of an initial loading
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
    readonly property Settings settings: appSettings
    Dialogs.Dialog {
        id: settingsDialog
        title: 'Settings'
        standardButtons: Dialogs.StandardButton.Save | Dialogs.StandardButton.Cancel | Dialogs.StandardButton.Reset
        GridLayout {
            columns: 2

            Label {
                Layout.preferredWidth: 140
                text: 'Editor'
            }
            TextField {
                id: editor
                placeholderText: "e.g. atom"
            }

            Label {
                Layout.preferredWidth: 140
                text: 'Verbose output'
            }
            CheckBox {
                id: verbose
                leftPadding: -3
            }

            Label {
                Layout.preferredWidth: 140
                text: 'Notifications'
            }
            CheckBox {
                id: notifications
                leftPadding: -3
            }
            Item { Layout.preferredWidth: 140 }  // spacer
            Text {
                Layout.preferredWidth: 250  // Detected recursive rearrange. Aborting after two iterations
                wrapMode: Text.Wrap
                color: 'dimgray'
                text: "Get messages about completed project actions when the app is in the background"
            }

            Text {
                Layout.columnSpan: 2
                Layout.maximumWidth: 250
                topPadding: 30
                bottomPadding: 10
                wrapMode: Text.Wrap
                text: 'To clear ALL app settings including the list of added projects click "Reset" then restart the app'
            }
        }
        // Set UI values there so they are always reflect the actual parameters
        onVisibleChanged: {
            if (visible) {
                editor.text = settings.get('editor');
                verbose.checked = settings.get('verbose');
                notifications.checked = settings.get('notifications');
            }
        }
        onAccepted: {
            settings.set('editor', editor.text);
            settings.set('verbose', verbose.checked);
            if (settings.get('notifications') !== notifications.checked) {
                settings.set('notifications', notifications.checked);
                sysTrayIcon.visible = notifications.checked;
            }
        }
        onReset: {
            settings.clear();
            this.close();
        }
    }

    Dialogs.Dialog {
        id: aboutDialog
        title: 'About'
        standardButtons: Dialogs.StandardButton.Close
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
                           <a href='https://github.com/ussserrr/stm32pio'>GitHub</a><br><br>
                           Powered by Python3, PlatformIO, Qt for Python, FlatIcons and other awesome technologies`
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

    /*
       The project visual representation is, in fact, split in two main parts: one in a list and one is
       an actual workspace. To avoid some possible bloopers we should make sure that both of them are loaded
       (at least at the subsistence level) before performing any actions with the project. To not reveal these
       QML-side implementation details to the backend we define this helper function that counts and stores
       a number of widgets currently loaded for each project in model and informs the Qt-side right after all
       necessary components become ready.

       TODO: should be remade to use Python id() as a unique identifier, see TODO.md
    */
    readonly property var initInfo: ({})
    function setInitInfo(projectIndex) {
        if (projectIndex in initInfo) {
            initInfo[projectIndex]++;
        } else {
            initInfo[projectIndex] = 1;
        }

        if (initInfo[projectIndex] === 2) {
            delete initInfo[projectIndex];  // index can be reused
            projectsModel.get(projectIndex).qmlLoaded();
        }
    }

    function removeCurrentProject() {
        const indexToRemove = projectsListView.currentIndex;
        indexToRemove === 0 ? projectsListView.incrementCurrentIndex() : projectsListView.decrementCurrentIndex();
        projectsModel.removeProject(indexToRemove);
    }

    menuBar: MenuBar {
        Menu {
            title: '&Menu'
            Action { text: '&Settings'; onTriggered: settingsDialog.open() }
            Action { text: '&About'; onTriggered: aboutDialog.open() }
            MenuSeparator { }
            // Use mainWindow.close() instead of Qt.quit() to prevent segfaults (messed up shutdown order)
            Action { text: '&Quit'; onTriggered: mainWindow.close() }
        }
    }

    Labs.SystemTrayIcon {
        id: sysTrayIcon
        icon.source: './icons/icon.svg'
        visible: settings.get('notifications')
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
            Overlay.modal: Rectangle { color: "#aaffffff" }
            contentItem: Column {
                spacing: 20
                Image {
                    id: dropPopupContent
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: './icons/drop-here.svg'
                    fillMode: Image.PreserveAspectFit
                    sourceSize.width: 64
                }
                Text {
                    text: "Drop projects folders to add..."
                    font.pointSize: 24  // different on different platforms, Qt's bug
                    font.weight: Font.Black  // heaviest
                }
            }
        }
        onDropped: {
            if (drop.urls.length) {
                // We need to convert to the array of strings as typeof(drop.urls) === 'object'
                projectsModel.addProjectByPath(Object.keys(drop.urls).map(u => drop.urls[u]));
            } else if (drop.text) {
                // Wrap into the array for consistency
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
                keyNavigationWraps: true

                highlight: Rectangle { color: 'darkseagreen' }
                highlightMoveDuration: 0  // turn off animations
                highlightMoveVelocity: -1

                model: projectsModel  // backend-side
                delegate: Component {
                    /*
                       (See setInitInfo docs) One of the two main widgets representing the project. Use Loader component
                       as it can give us the relible timestamp of all its children loading completion (unlike Component.onCompleted)
                    */
                    id: listViewDelegate
                    Loader {
                        onLoaded: setInitInfo(index)
                        sourceComponent: RowLayout {
                            property bool initLoading: true  // initial waiting for the backend-side TODO: do not store state in the delegate!
                            readonly property ProjectListItem project: projectsModel.get(index)
                            Connections {
                                target: project
                                // Currently, this event is equivalent to the complete initialization of the backend side of the project
                                onNameChanged: {
                                    initLoading = false;

                                    // Appropriately highlight an item depending on its initialization result
                                    const state = project.state;
                                    if (state['INIT_ERROR']) {
                                        projectName.color = 'indianred';
                                        projectCurrentStage.color = 'indianred';
                                    } else if (!project.fromStartup && projectsModel.rowCount() > 1 && index !== projectsListView.currentIndex) {
                                        // Do not touch those projects that have been loaded on startup (from the QSettings), only the new ones
                                        // added during this session. Also, do not highlight if there is only a single element in the list or
                                        // the list is already located to this item
                                        projectName.color = 'seagreen';
                                        projectCurrentStage.color = 'seagreen';
                                    }
                                }
                                onActionStarted: {
                                    runningOrFinished.currentIndex = 0;
                                    runningOrFinished.visible = true;
                                }
                                onActionFinished: {
                                    if (index !== projectsListView.currentIndex) {
                                        projectCurrentStage.color = 'darkgray';  // show that the stage has changed from the last visit
                                        runningOrFinished.currentIndex = 1;  // show "notification" about the finished action
                                        recentlyFinishedIndicator.color = success ? 'lightgreen' : 'lightcoral';
                                        runningOrFinished.visible = true;
                                    } else {
                                        runningOrFinished.visible = false;
                                    }
                                }
                            }
                            Connections {
                                target: projectsListView
                                onCurrentIndexChanged: {
                                    // "Read" all "notifications" after navigating to the list element
                                    if (projectsListView.currentIndex === index) {
                                        if (Qt.colorEqual(projectName.color, 'seagreen')) {
                                            projectName.color = 'black';
                                            projectCurrentStage.color = 'black';
                                        }
                                        if (Qt.colorEqual(projectCurrentStage.color, 'darkgray')) {
                                            projectCurrentStage.color = 'black';
                                            runningOrFinished.visible = false;
                                        }
                                    }
                                }
                            }
                            ColumnLayout {
                                Layout.preferredHeight: 50

                                Text {
                                    id: projectName
                                    leftPadding: 5
                                    rightPadding: runningOrFinished.visible ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.preferredWidth: runningOrFinished.visible ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideMiddle
                                    maximumLineCount: 1
                                    text: `<b>${display.name}</b>`
                                }
                                Text {
                                    id: projectCurrentStage
                                    leftPadding: 5
                                    rightPadding: runningOrFinished.visible ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignTop
                                    Layout.preferredWidth: runningOrFinished.visible ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                    text: display.currentStage
                                }
                            }

                            // Show whether a busy indicator or a finished action notification
                            StackLayout {
                                // TODO: probably can use DSM.StateMachine (or maybe regular State) for this, too
                                id: runningOrFinished
                                Layout.alignment: Qt.AlignVCenter
                                Layout.preferredWidth: parent.height
                                Layout.preferredHeight: parent.height
                                visible: parent.initLoading  // initial binding

                                BusyIndicator {
                                    // Important note: if you toggle visibility frequently better use 'visible'
                                    // instead of 'running' for stable visual appearance
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                }
                                Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Rectangle {  // Circle :)
                                        id: recentlyFinishedIndicator
                                        anchors.centerIn: parent
                                        width: 10
                                        height: width
                                        radius: width * 0.5
                                    }
                                }
                            }

                            MouseArea {
                                x: parent.x
                                y: parent.y
                                width: parent.width
                                height: parent.height
                                enabled: !parent.initLoading
                                onClicked: projectsListView.currentIndex = index
                            }
                        }
                    }
                }

                Labs.FolderDialog {
                    id: addProjectFolderDialog
                    currentFolder: Labs.StandardPaths.standardLocations(Labs.StandardPaths.HomeLocation)[0]
                    onAccepted: projectsModel.addProjectByPath([folder])
                }
                footerPositioning: ListView.OverlayFooter
                footer: Rectangle {  // Probably should use Pane but need to override default window color then
                    z: 2
                    width: projectsListView.width
                    implicitHeight: listFooter.implicitHeight
                    color: mainWindow.color
                    RowLayout {
                        id: listFooter
                        anchors.centerIn: parent
                        Connections {
                            target: projectsModel
                            // Just added project is already in the list so abort the addition and jump to the existing one
                            onDuplicateFound: projectsListView.currentIndex = duplicateIndex
                        }
                        Button {
                            text: 'Add'
                            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                            display: AbstractButton.TextBesideIcon
                            icon.source: './icons/add.svg'
                            onClicked: addProjectFolderDialog.open()
                            ToolTip.visible: projectsListView.count === 0 && !loadingOverlay.visible  // show when there is no items in the list
                            ToolTip.text: "<b>Hint:</b> add your project using this button or drag'n'drop it into the window"
                        }
                        Button {
                            text: 'Remove'
                            visible: projectsListView.currentIndex !== -1  // show only if any item is selected
                            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                            display: AbstractButton.TextBesideIcon
                            icon.source: './icons/remove.svg'
                            onClicked: removeCurrentProject()
                        }
                    }
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

            Connections {
                target: projectsListView
                onCurrentIndexChanged: projectsWorkspaceView.currentIndex = projectsListView.currentIndex
            }
            Repeater {
                // Use similar to ListView pattern (same projects model, Loader component)
                model: projectsModel
                delegate: Component {
                    Loader {
                        property int projectIndex: index  // binding so will be automatically updated on change
                        onLoaded: setInitInfo(index)
                        /*
                           Use another one StackLayout to separate Project initialization "screen" and Main one
                        */
                        sourceComponent: StackLayout {
                            id: mainOrInitScreen
                            currentIndex: -1  // at widget creation we do not show main nor init screen

                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            readonly property ProjectListItem project: projectsModel.get(index)

                            /*
                               State retrieving procedure is relatively expensive (many IO operations) so we optimize it by getting the state
                               only in certain situations (see Component.onCompleted below) and caching a value in the local varible. Then, all
                               widgets can pick up this value as many times as they want while not abusing the real property getter. Such a subscription
                               can be established by the creation of a local reference to the cache and listening to the change event like this:

                                    property var stateCachedNotifier: stateCached
                                    onStateCachedNotifierChanged: {
                                        // use stateCached there
                                    }
                            */
                            signal handleState()
                            property var stateCached: ({})
                            onHandleState: {
                                if (mainWindow.active &&  // the app got foreground
                                    projectIndex === projectsWorkspaceView.currentIndex &&  // only for the current list item
                                    !projectIncorrectDialog.visible &&  // on macOS, there is an animation effect so this property isn't updated
                                                                        // immediately and the state can be retrieved several times and some flaws
                                                                        // may appear. Workaround - is to have a dedicated flag and update it
                                                                        // manually but this isn't very elegant solution
                                    project.currentAction === ''
                                ) {
                                    const state = project.state;
                                    stateCached = state;

                                    project.stageChanged();  // side-effect: update the stage at the same time
                                }
                            }
                            Component.onCompleted: {
                                // Several events lead to a single handler
                                project.stateChanged.connect(handleState);  // the model has notified about the change
                                projectsWorkspaceView.currentIndexChanged.connect(handleState);  // the project was selected in the list
                                mainWindow.activeChanged.connect(handleState);  // the app window has got (or lost, filter in the handler) the focus
                            }

                            Connections {
                                target: project
                                // Currently, this event is equivalent to the complete initialization of the backend side of the project
                                onNameChanged: {
                                    const state = project.state;
                                    const completedStages = Object.keys(state).filter(stateName => state[stateName]);
                                    if (completedStages.length === 1 && completedStages[0] === 'EMPTY') {
                                        setupScreenLoader.active = true;
                                        mainOrInitScreen.currentIndex = 0;  // show init dialog
                                    } else {
                                        mainOrInitScreen.currentIndex = 1;  // show main view
                                    }
                                }
                            }

                            // property bool projectIncorrectDialogIsOpen: false
                            Dialogs.MessageDialog {
                                id: projectIncorrectDialog
                                visible: Object.keys(stateCached).length && !stateCached['INIT_ERROR'] && !stateCached['EMPTY']
                                text: `The project was modified outside of the stm32pio and .ioc file is no longer present.<br>
                                       The project will be removed from the app. It will not affect any real content`
                                icon: Dialogs.StandardIcon.Critical
                                onAccepted: removeCurrentProject()
                            }

                            /*
                               Index: 0. Project initialization "screen"

                               Prompt a user to perform initial setup
                            */
                            Loader {
                                id: setupScreenLoader
                                active: false
                                sourceComponent: Column {
                                    Text {
                                        text: "To complete initialization you can provide the PlatformIO name of the board"
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
                                            onAccepted: focus = false
                                            onActivated: focus = false
                                            onFocusChanged: {
                                                if (focus) {
                                                    selectAll();
                                                } else {
                                                    if (find(editText) === -1) {
                                                        editText = textAt(0);  // should be 'None' at index 0
                                                    }
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
                                                visible: runCheckBox.hovered  // not working on Linux (Manjaro LXQt)
                                                Component.onCompleted: {
                                                    // Form the tool tip text using action names
                                                    const actions = [];
                                                    for (let i = projActionsModel.statefulActionsStartIndex; i < projActionsModel.count; ++i) {
                                                        actions.push(`<b>${projActionsModel.get(i).name}</b>`);
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
                                                visible: openEditor.hovered  // not working on Linux (Manjaro LXQt)
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
                                            // All 'run' operations will be queued by the backend
                                            project.run('save_config', [{
                                                'project': {
                                                    'board': board.editText === board.textAt(0) ? '' : board.editText
                                                }
                                            }]);
                                            if (board.editText === board.textAt(0)) {
                                                project.logAdded('WARNING  STM32 PlatformIO board is not specified, it will be needed on PlatformIO ' +
                                                                 'project creation. You can set it in "stm32pio.ini" file in the project directory',
                                                                 Logging.WARNING);
                                            }

                                            if (runCheckBox.checked) {
                                                for (let i = projActionsModel.statefulActionsStartIndex + 1; i < projActionsModel.count; ++i) {
                                                    project.run(projActionsModel.get(i).action, []);
                                                }
                                            }

                                            if (openEditor.checked) {
                                                project.run('start_editor', [settings.get('editor')]);
                                            }

                                            mainOrInitScreen.currentIndex = 1;  // go to main screen
                                            setupScreenLoader.sourceComponent = undefined;  // destroy init screen
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

                                /*
                                   Show this or action buttons
                                */
                                Text {
                                    id: initErrorMessage
                                    visible: stateCached['INIT_ERROR'] ? true : false  // explicitly convert to boolean
                                    padding: 10
                                    text: "<b>The project cannot be initialized</b>"
                                    color: 'indianred'
                                }

                                /*
                                   The core widget - a group of buttons mapping all main actions that can be performed on the given project.
                                   They also serve the project state displaying - each button indicates a stage associated with it:
                                    - green (and green glow): done
                                    - yellow: in progress right now
                                    - red glow: an error has occured during the last execution
                                */
                                RowLayout {
                                    id: projActionsRow
                                    visible: stateCached['INIT_ERROR'] ? false : true
                                    Layout.fillWidth: true
                                    Layout.bottomMargin: 7
                                    z: 1  // for the glowing animation
                                    Repeater {
                                        model: ListModel {
                                            id: projActionsModel
                                            readonly property int statefulActionsStartIndex: 2
                                            ListElement {
                                                name: 'Clean'
                                                action: 'clean'
                                                tooltip: "<b>WARNING:</b> this will delete <b>ALL</b> content of the project folder \
                                                          except the current .ioc file and clear all logs"
                                            }
                                            ListElement {
                                                name: 'Open editor'
                                                action: 'start_editor'
                                                margin: 15  // margin to visually separate first 2 actions as they don't represent any stage
                                            }
                                            ListElement {
                                                name: 'Initialize'
                                                stageRepresented: 'INITIALIZED'  // the project stage this button is representing
                                                action: 'save_config'
                                            }
                                            ListElement {
                                                name: 'Generate'
                                                stageRepresented: 'GENERATED'
                                                action: 'generate_code'
                                            }
                                            ListElement {
                                                name: 'Init PlatformIO'
                                                stageRepresented: 'PIO_INITIALIZED'
                                                action: 'pio_init'
                                            }
                                            ListElement {
                                                name: 'Patch'
                                                stageRepresented: 'PATCHED'
                                                action: 'patch'
                                            }
                                            ListElement {
                                                name: 'Build'
                                                stageRepresented: 'BUILT'
                                                action: 'build'
                                            }
                                        }
                                        delegate: Button {
                                            text: model.name
                                            Layout.rightMargin: model.margin
                                            property bool shouldBeHighlighted: false  // highlight on mouse over
                                            property bool shouldBeHighlightedWhileRunning: false  // distinguish actions picked out for the batch run
                                            property int buttonIndex: -1
                                            Component.onCompleted: {
                                                buttonIndex = index;
                                                background.border.color = 'dimgray';
                                            }
                                            ToolTip {
                                                visible: mouseArea.containsMouse
                                                Component.onCompleted: {
                                                    if (model.tooltip) {
                                                        text = model.tooltip;
                                                    } else {
                                                        this.destroy();
                                                    }
                                                }
                                            }
                                            onClicked: {
                                                // JS array cannot be attached to a ListElement (at least in a non-hacky manner) so we fill arguments here
                                                const args = [];
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
                                            /*
                                               As the button reflects relatively complex logic it's easier to maintain using the state machine technique.
                                               We define states and allowed transitions between them, all other stuff is managed by the DSM framework.
                                               You can find the graphical diagram somewhere in the docs
                                            */
                                            DSM.StateMachine {
                                                initialState: main  // start position
                                                running: true  // run immediately
                                                DSM.State {
                                                    id: main
                                                    initialState: normal
                                                    DSM.SignalTransition {
                                                        targetState: disabled
                                                        signal: project.actionStarted
                                                    }
                                                    DSM.SignalTransition {
                                                        targetState: highlighted
                                                        signal: shouldBeHighlightedChanged
                                                        guard: shouldBeHighlighted  // go only if...
                                                    }
                                                    onEntered: {
                                                        enabled = true;
                                                        palette.buttonText = 'black';
                                                    }
                                                    DSM.State {
                                                        id: normal
                                                        DSM.SignalTransition {
                                                            targetState: stageFulfilled
                                                            signal: stateCachedChanged
                                                            guard: stateCached[model.stageRepresented] ? true : false  // explicitly convert to boolean
                                                        }
                                                        onEntered: {
                                                            palette.button = 'lightgray';
                                                        }
                                                    }
                                                    DSM.State {
                                                        id: stageFulfilled
                                                        DSM.SignalTransition {
                                                            targetState: normal
                                                            signal: stateCachedChanged
                                                            guard: stateCached[model.stageRepresented] ? false : true
                                                        }
                                                        onEntered: {
                                                            palette.button = 'lightgreen';
                                                        }
                                                    }
                                                    DSM.HistoryState {
                                                        id: mainHistory
                                                        defaultState: normal
                                                    }
                                                }
                                                DSM.State {
                                                    // Activates/deactivates additional properties (such as color or border) on some conditions
                                                    // (e.g. some action is currently running), see onEntered, onExited
                                                    id: disabled
                                                    DSM.SignalTransition {
                                                        targetState: mainHistory
                                                        signal: project.actionFinished
                                                    }
                                                    onEntered: {
                                                        enabled = false;
                                                        palette.buttonText = 'darkgray';
                                                        if (project.currentAction === model.action) {
                                                            palette.button = 'gold';
                                                        }
                                                        if (shouldBeHighlightedWhileRunning) {
                                                            background.border.width = 2;
                                                        }
                                                    }
                                                    onExited: {
                                                        // Erase highlighting if this action is last in the series or at all
                                                        if (project.currentAction === model.action &&
                                                            shouldBeHighlightedWhileRunning &&
                                                            (buttonIndex === (projActionsModel.count - 1) ||
                                                             projActionsRow.children[buttonIndex + 1].shouldBeHighlightedWhileRunning === false)
                                                        ) {
                                                            for (let i = projActionsModel.statefulActionsStartIndex; i <= buttonIndex; ++i) {
                                                                projActionsRow.children[i].shouldBeHighlightedWhileRunning = false;
                                                                projActionsRow.children[i].background.border.width = 0;
                                                            }
                                                        }
                                                    }
                                                }
                                                DSM.State {
                                                    id: highlighted
                                                    DSM.SignalTransition {
                                                        targetState: mainHistory
                                                        signal: shouldBeHighlightedChanged
                                                        guard: !shouldBeHighlighted
                                                    }
                                                    onEntered: {
                                                        palette.button = Qt.lighter('lightgreen', 1.2);
                                                        palette.buttonText = 'dimgray';
                                                    }
                                                }
                                            }
                                            /*
                                               Detect modifier keys using overlayed MouseArea:
                                                - Ctrl (Cmd): start the editor after the action(s)
                                                - Shift: batch actions run
                                            */
                                            MouseArea {
                                                id: mouseArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                property bool ctrlPressed: false
                                                property bool ctrlPressedLastState: false
                                                property bool shiftPressed: false
                                                property bool shiftPressedLastState: false
                                                function shiftHandler() {
                                                    // manage the appearance of all [stateful] buttons prior this one
                                                    for (let i = projActionsModel.statefulActionsStartIndex; i <= buttonIndex; ++i) {
                                                        projActionsRow.children[i].shouldBeHighlighted = shiftPressed;
                                                    }
                                                }
                                                onClicked: {
                                                    if (shiftPressed && buttonIndex >= projActionsModel.statefulActionsStartIndex) {
                                                        for (let i = projActionsModel.statefulActionsStartIndex; i <= buttonIndex; ++i) {
                                                            projActionsRow.children[i].shouldBeHighlighted = false;
                                                            projActionsRow.children[i].shouldBeHighlightedWhileRunning = true;
                                                        }
                                                        for (let i = projActionsModel.statefulActionsStartIndex; i < buttonIndex; ++i) {
                                                            project.run(projActionsModel.get(i).action, []);
                                                        }
                                                    }
                                                    parent.clicked();  // pass the event to the underlying button though all work can be done in-place
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
                                                    if (shiftPressedLastState !== shiftPressed) {  // reduce a number of unnecessary shiftHandler() calls
                                                        shiftPressedLastState = shiftPressed;
                                                        shiftHandler();
                                                    }
                                                }
                                                onEntered: {
                                                    if (model.action !== 'start_editor') {
                                                        let preparedText = `<b>Ctrl</b>-click to open the editor specified in the <b>Settings</b>
                                                                            after the operation`;
                                                        if (buttonIndex >= projActionsModel.statefulActionsStartIndex) {
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
                                            }
                                            Connections {
                                                target: project
                                                onActionStarted: {
                                                    glow.visible = false;
                                                }
                                                onActionFinished: {
                                                    if (action === model.action) {
                                                        if (success) {
                                                            glow.color = 'lightgreen';
                                                        } else {
                                                            glow.color = 'lightcoral';
                                                        }
                                                        glow.visible = true;

                                                        if (settings.get('notifications') && !mainWindow.active) {
                                                            sysTrayIcon.showMessage(
                                                                success ? 'Success' : 'Error',  // title
                                                                `${project.name} - ${model.name}`,  // text
                                                                success ? Labs.SystemTrayIcon.Information : Labs.SystemTrayIcon.Warning,  // icon
                                                                5000  // ms
                                                            );
                                                        }
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
                                                onVisibleChanged: visible ? glowAnimation.start() : glowAnimation.complete()
                                                SequentialAnimation {
                                                    id: glowAnimation
                                                    loops: 3
                                                    onStopped: glow.visible = false
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
                                            font.pointSize: 10  // different on different platforms, Qt's bug
                                            font.weight: Font.DemiBold
                                            textFormat: TextEdit.RichText
                                            Connections {
                                                target: project
                                                onLogAdded: {
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
                            }
                        }
                    }
                }
            }
        }
    }

    /*
       Improvised status bar - simple text line. Currently, doesn't support smart intrinsic properties
       as a fully-fledged status bar, but is used only for a single feature so not a big deal right now
    */
    footer: Text {
        id: statusBar
        padding: 10
    }
}
