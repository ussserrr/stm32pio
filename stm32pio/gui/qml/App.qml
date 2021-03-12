import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQml.Models 2.14
import QtQuick.Layouts 1.14
import QtGraphicalEffects 1.14
import QtQuick.Dialogs 1.3 as Dialogs
import QtQml.StateMachine 1.14 as DSM

import Qt.labs.platform 1.1 as Labs

import ProjectListItem 1.0
import Settings 1.0


ApplicationWindow {
    id: mainWindow
    visible: true
    minimumWidth: 980  // comfortable initial size for all platforms (as the same style is used for any of them)
    minimumHeight: 310
    height: 310  // 530
    title: 'stm32pio'
    color: 'whitesmoke'

    /*
       Notify the front about the end of an initial loading
    */
    signal backendLoaded(bool success)
    onBackendLoaded: {
        loadingOverlay.close();
        if (!success) {
            backendLoadingErrorDialog.open();
        }
    }
    Dialogs.MessageDialog {
        id: backendLoadingErrorDialog
        title: 'Warning'
        text: "There was an error during the initialization of the Python backend. Please see the terminal output for more details"
        icon: Dialogs.StandardIcon.Warning
    }
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

    AboutDialog {
        id: aboutDialog
        appVersion: appVersion
    }

    readonly property Settings settings: appSettings
    SettingsDialog {
        id: settingsDialog
        settings: settings
    }

    /*
       The project visual representation is, in fact, split in two main parts: one in a list and one is
       an actual workspace. To avoid some possible bloopers we should make sure that both of them are loaded
       (at least at the subsistence level) before performing any actions with the project. To not reveal these
       QML-side implementation details to the backend we define this helper function that counts and stores
       a number of widgets currently loaded for each project in model and informs the Qt-side right after all
       necessary components become ready.
    */
    readonly property var initInfo: ({})
    function setInitInfo(projectIndex) {
        if (projectIndex in initInfo) {
            initInfo[projectIndex]++;
        } else {
            initInfo[projectIndex] = 1;
        }

        if (initInfo[projectIndex] === 4) {  // TODO
            delete initInfo[projectIndex];  // index can be reused
            projectsModel.get(projectIndex).qmlLoaded();
        }
    }

    Connections {
        target: projectsModel
        function onGoToProject(indexToGo) {
            projectsListView.currentIndex = indexToGo;
        }
    }
    function removeCurrentProject() {
        const indexToRemove = projectsListView.currentIndex;
        indexToRemove === 0 ? projectsListView.incrementCurrentIndex() : projectsListView.decrementCurrentIndex();

        // Need to manually unload the dynamic component to prevent annoying "TypeError: Cannot read property 'XXX' of null" messages
        projectsWorkspaceView.children[indexToRemove].sourceComponent = undefined;

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
        icon.source: '../icons/icon.svg'
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
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: '../icons/drop-here.svg'
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
                // We need to convert to an array of strings since typeof(drop.urls) === 'object'
                projectsModel.addProjectsByPaths(Object.values(drop.urls));
            } else if (drop.text) {
                // Wrap into an array for consistency
                projectsModel.addProjectsByPaths([drop.text]);
            } else {
                console.warn("Incorrect drag'n'drop event");
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
            Layout.preferredWidth: 2.6 * parent.width / 12  // ~1/5, probably should reduce or at least cast to the fraction of 10
            Layout.fillHeight: true

            /*
               The dynamic list of projects (initially loaded from the QSettings, can be modified later)
            */
            ListView {
                id: projectsListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                keyNavigationWraps: true

                highlight: Rectangle { color: 'darkseagreen' }
                highlightMoveDuration: 0  // turn off animations
                highlightMoveVelocity: -1

                model: DelegateModel {
                    /*
                       Use DelegateModel as it has a feature to always preserve specified list items in memory so we can store an actual state
                       directly in the delegate
                    */
                    model: projectsModel  // backend-side
                    delegate: Loader {
                        /*
                           (See setInitInfo docs) One of the two main widgets representing the project. Use Loader component
                           as it can give us the reliable timestamp of all its children loading completion (unlike Component.onCompleted)
                        */
                        onLoaded: {
                            setInitInfo(index);
                            DelegateModel.inPersistedItems = 1;  // TODO: = true (5.15)
                        }
                        sourceComponent: RowLayout {
                            // TODO: maybe should use "display" (or custom) role everywhere so no need to specify "project" property
                            //  (but extensive list.data() usage then)
                            // readonly property ProjectListItem project: projectsModel.get(index)
                            ColumnLayout {
                                Layout.preferredHeight: 50

                                Text {
                                    id: projectName
                                    leftPadding: 5
                                    rightPadding: actionIndicator.visible ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.preferredWidth: actionIndicator.visible ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideMiddle
                                    maximumLineCount: 1
                                    text: `<b>${display.name}</b>`
                                    DSM.StateMachine {
                                        running: true
                                        initialState: normall
                                        onStarted: {
                                            setInitInfo(index);
                                        }
                                        DSM.State {
                                            id: normall
                                            onEntered: {
                                                projectName.color = 'black';
                                            }
                                            DSM.SignalTransition {
                                                targetState: added
                                                signal: display.actionFinished
                                                guard: action === 'initialization' && success && !display.fromStartup && projectsListView.currentIndex !== index
                                            }
                                            DSM.SignalTransition {
                                                targetState: initializationErrorr
                                                signal: display.actionFinished
                                                guard: action === 'initialization' && !success
                                            }
                                        }
                                        DSM.State {
                                            id: added
                                            onEntered: {
                                                projectName.color = 'seagreen';
                                            }
                                            DSM.SignalTransition {
                                                targetState: normall
                                                signal: projectsListView.currentIndexChanged
                                                guard: projectsListView.currentIndex === index
                                            }
                                        }
                                        DSM.FinalState {
                                            id: initializationErrorr
                                            onEntered: {
                                                projectName.color = 'indianred';
                                            }
                                        }
                                    }
                                }
                                Text {
                                    id: projectCurrentStage
                                    leftPadding: 5
                                    rightPadding: actionIndicator.visible ? 0 : leftPadding
                                    Layout.alignment: Qt.AlignTop
                                    Layout.preferredWidth: actionIndicator.visible ?
                                                           (projectsListView.width - parent.height - leftPadding) :
                                                           projectsListView.width
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                    text: display.currentStage
                                    DSM.StateMachine {
                                        running: true
                                        initialState: navigated
                                        onStarted: {
                                            setInitInfo(index);
                                        }
                                        DSM.State {
                                            id: navigated
                                            onEntered: {
                                                projectCurrentStage.color = 'black';
                                            }
                                            DSM.SignalTransition {
                                                targetState: inactive
                                                signal: projectsListView.currentIndexChanged
                                                guard: projectsListView.currentIndex !== index
                                            }
                                            DSM.SignalTransition {
                                                targetState: inactive
                                                signal: display.actionFinished
                                                guard: action === 'initialization' && success && projectsListView.currentIndex !== index && display.fromStartup
                                            }
                                            DSM.SignalTransition {
                                                targetState: addedd
                                                signal: display.actionFinished
                                                guard: action === 'initialization' && success && projectsListView.currentIndex !== index && !display.fromStartup
                                            }
                                            DSM.SignalTransition {
                                                targetState: initializationError
                                                signal: display.actionFinished
                                                guard: action === 'initialization' && !success
                                            }
                                        }
                                        DSM.State {
                                            id: addedd
                                            onEntered: {
                                                projectCurrentStage.color = 'seagreen';
                                            }
                                            DSM.SignalTransition {
                                                targetState: navigated
                                                signal: projectsListView.currentIndexChanged
                                                guard: projectsListView.currentIndex === index
                                            }
                                        }
                                        DSM.State {
                                            id: inactive
                                            onEntered: {
                                                projectCurrentStage.color = 'darkgray';
                                            }
                                            DSM.SignalTransition {
                                                targetState: navigated
                                                signal: projectsListView.currentIndexChanged
                                                guard: projectsListView.currentIndex === index
                                            }
                                        }
                                        DSM.FinalState {
                                            id: initializationError
                                            onEntered: {
                                                projectCurrentStage.color = 'indianred';
                                            }
                                        }
                                    }
                                }
                            }

                            // Show whether a busy indicator or a finished action notification
                            StackLayout {
                                id: actionIndicator
                                Layout.alignment: Qt.AlignVCenter
                                Layout.preferredWidth: parent.height
                                Layout.preferredHeight: parent.height

                                DSM.StateMachine {
                                    running: true  // run immediately
                                    initialState: busy  // seems like initialization process starts earlier then StateMachine runs so lets start from "busy"
                                    onStarted: {
                                        setInitInfo(index);
                                    }
                                    DSM.State {
                                        id: normal
                                        onEntered: {
                                            actionIndicator.visible = false;
                                        }
                                        DSM.SignalTransition {
                                            targetState: busy
                                            signal: display.actionStarted
                                        }
                                    }
                                    DSM.State {
                                        id: busy
                                        onEntered: {
                                            actionIndicator.currentIndex = 0;
                                            actionIndicator.visible = true;
                                        }
                                        DSM.SignalTransition {
                                            targetState: normal
                                            signal: display.actionFinished
                                            guard: projectsListView.currentIndex === index || action === 'initialization'
                                        }
                                        DSM.SignalTransition {
                                            targetState: indication
                                            signal: display.actionFinished
                                        }
                                    }
                                    DSM.State {
                                        id: indication
                                        onEntered: {
                                            actionIndicator.currentIndex = 1;
                                        }
                                        DSM.SignalTransition {
                                            targetState: normal
                                            signal: projectsListView.currentIndexChanged
                                            guard: projectsListView.currentIndex === index
                                        }
                                    }
                                }

                                BusyIndicator {
                                    // Important note: if you toggle visibility frequently better use 'visible'
                                    // instead of 'running' for a stable visual appearance
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                }
                                Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Rectangle {  // Circle :)
                                        anchors.centerIn: parent
                                        width: 10
                                        height: width
                                        radius: width * 0.5
                                        color: display.lastActionSucceed ? 'lightgreen' : 'lightcoral'
                                    }
                                }
                            }

                            MouseArea {
                                x: parent.x
                                y: parent.y
                                width: parent.width
                                height: parent.height
                                onClicked: projectsListView.currentIndex = index
                            }
                        }
                    }
                }

                Labs.FolderDialog {
                    id: addProjectFolderDialog
                    currentFolder: Labs.StandardPaths.standardLocations(Labs.StandardPaths.HomeLocation)[0]
                    onAccepted: projectsModel.addProjectsByPaths([folder])
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
                        Button {
                            text: 'Add'
                            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                            display: AbstractButton.TextBesideIcon
                            icon.source: '../icons/add.svg'
                            onClicked: addProjectFolderDialog.open()
                            ToolTip.visible: projectsListView.count === 0  // show when there is no items in the list
                            ToolTip.text: "<b>Hint:</b> add your project using this button or drag'n'drop it into the window"
                        }
                        Button {
                            text: 'Remove'
                            visible: projectsListView.currentIndex !== -1  // show only if any item is selected
                            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                            display: AbstractButton.TextBesideIcon
                            icon.source: '../icons/remove.svg'
                            onClicked: removeCurrentProject()
                        }
                    }
                }
            }
        }


        /*
           Main workspace. StackLayout's Repeater component seamlessly uses the same projects model (showing one -
           current - project per screen) as the list so all data is synchronized without any additional effort
        */
        StackLayout {
            id: projectsWorkspaceView
            Layout.preferredWidth: 9.4 * parent.width / 12
            Layout.fillHeight: true
            Layout.leftMargin: 5
            Layout.rightMargin: 10
            Layout.topMargin: 10
            currentIndex: projectsListView.currentIndex

            Repeater {
                // Use similar to ListView pattern (same projects model, Loader component)
                model: projectsModel
                delegate: Loader {
                    // active: index === projectsWorkspaceView.currentIndex
                    // onLoaded: setInitInfo(index)

                    sourceComponent: Item {
                        BusyIndicator {
                            anchors.centerIn: parent
                        }
                    }

                    readonly property ProjectListItem project: projectsModel.get(index)

                    signal handleState()
                    property var stateCached: ({})
                    onHandleState: {
                        if (mainWindow.active &&  // the app got foreground
                            index === projectsWorkspaceView.currentIndex &&  // only for the current list item
                            !projectIncorrectDialog.visible &&  // on macOS, there is an animation effect so this property isn't updated
                                                                // immediately and the state can be retrieved several times and some flaws
                                                                // may appear. Workaround - is to have a dedicated flag and update it
                                                                // manually but this isn't very elegant solution
                            display.currentAction === ''
                        ) {
                            const state = display.state;
                            stateCached = state;

                            display.stageChanged();  // side-effect: update the stage at the same time
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
                        function onInitialized() {
                            const state = project.state;
                            stateCached = state;
                            const completedStages = Object.keys(state).filter(stateName => state[stateName]);
                            if (completedStages.length === 1 && completedStages[0] === 'EMPTY') {
                                sourceComponent = projectSetupPage;
                            } else {
                                const config = project.config;
                                if (Object.keys(config['project']).length && !config['project']['board']) {
                                    // TODO: stm32pio.ini is hard-coded here though it is a parameter (settings.py)
                                    project.logAdded('WARNING  STM32 PlatformIO board is not specified, it will be needed on PlatformIO ' +
                                                     'project creation. You can set it in "stm32pio.ini" file in the project directory',
                                                     Logging.WARNING);
                                }
                                sourceComponent = workspacePage;
                            }
                        }
                    }

                    // TODO: Maybe use initErrorMessage for this
                    Dialogs.MessageDialog {
                        id: projectIncorrectDialog
                        visible: Object.keys(stateCached).length && [
                                     'LOADING',  // ignore transitional state
                                     'INIT_ERROR',  // we have another view for this state, skip
                                     'EMPTY'  // true if .ioc file is present, false otherwise
                                 ].every(key => !stateCached[key])
                        text: `The project was modified outside of the stm32pio and .ioc file is no longer present.<br>
                                The project will be removed from the app. It will not affect any real content`
                        icon: Dialogs.StandardIcon.Warning
                        onAccepted: removeCurrentProject()
                    }

                    ListModel {
                        id: projActionsModel
                        readonly property int statefulActionsStartIndex: 2
                        ListElement {
                            name: 'Clean'
                            action: 'clean'
                            icon: '../icons/trash-bin.svg'
                            tooltip: "<b>WARNING:</b> this will delete <b>ALL</b> content of the project folder \
                                      except the current .ioc file and clear all logs"
                        }
                        ListElement {
                            name: 'Open editor'
                            action: 'start_editor'
                            icon: '../icons/edit.svg'
                            margin: 15  // margin to visually separate first 2 actions as they don't represent any stage
                        }
                        ListElement {
                            name: 'Initialize'
                            stageRepresented: 'INITIALIZED'  // the project stage this button is representing
                            action: 'save_config'
                            // TODO: stm32pio.ini is hard-coded here though it is a parameter (settings.py)
                            tooltip: "Saves the current configuration to the config file <b>stm32pio.ini</b>"
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


                    Component {
                        id: projectSetupPage
                        Column {
                            topPadding: 10
                            leftPadding: 10
                            spacing: 11
                            Text {
                                text: "To complete project initialization you can provide the PlatformIO name of the board:"
                            }
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
                                            editText = textAt(0);  // should be 'None' at index 0 (TODO probably)
                                        }
                                    }
                                }
                                Component.onCompleted: {
                                    // Board can be already specified in the config, in this case we should paste it
                                    const config = project.config;
                                    if (Object.keys(config['project']).length && config['project']['board']) {
                                        editText = config['project']['board'];
                                    }
                                    forceActiveFocus();
                                }
                                // KeyNavigation.tab: openEditor  // not working...
                            }
                            Text {
                                text: "Additional actions to perform next:"
                                topPadding: 10
                            }
                            Row {
                                topPadding: -6
                                leftPadding: -6
                                spacing: 10
                                /*
                                    Trigger full run
                                */
                                CheckBox {
                                    id: runCheckBox
                                    text: 'Full run'
                                    enabled: false
                                    ToolTip {
                                        visible: runCheckBox.hovered  // not working on Linux (Manjaro LXQt)
                                        Component.onCompleted: {
                                            // Form the tool tip text using action names
                                            const actions = [];
                                            for (let i = projActionsModel.statefulActionsStartIndex; i < projActionsModel.count; ++i) {
                                                actions.push(`<b>${projActionsModel.get(i).name}</b>`);
                                            }
                                            text = `Execute tasks: ${actions.join(' → ')}`;
                                        }
                                    }
                                    Connections {
                                        target: board
                                        function onFocusChanged() {
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
                                topInset: 14
                                topPadding: 20
                                onClicked: {
                                    // All 'run' operations will be queued by the backend
                                    project.run('save_config', [{
                                        'project': {
                                            'board': board.editText === board.textAt(0) ? '' : board.editText
                                        }
                                    }]);

                                    if (board.editText === board.textAt(0)) {
                                        // TODO: stm32pio.ini is hard-coded here though it is a parameter (settings.py)
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

                                    sourceComponent = workspacePage;
                                }
                            }
                        }
                    }

                    Component {
                        id: workspacePage
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            Loader {
                                sourceComponent: stateCached['INIT_ERROR'] ? initErrorMessage : projActionsRowC
                            }

                            /*
                                Show this or action buttons
                            */
                            Component {
                                id: initErrorMessage
                                Text {
                                    padding: 10
                                    text: "<b>The project cannot be initialized</b>"
                                    color: 'indianred'
                                }
                            }

                            /*
                                The core widget - a group of buttons mapping all main actions that can be performed on the given project.
                                They also serve the project state displaying - each button indicates a stage associated with it:
                                    - green (and green glow): done
                                    - yellow: in progress right now
                                    - red glow: an error has occurred during the last execution
                            */
                            Component {
                                id: projActionsRowC
                                RowLayout {
                                    id: projActionsRow
                                    Layout.fillWidth: true
                                    Layout.bottomMargin: 7
                                    z: 1  // for the glowing animation
                                    Repeater {
                                        model: projActionsModel
                                        delegate: Button {
                                            text: model.name
                                            Layout.rightMargin: model.margin
                                            property bool shouldBeHighlighted: false  // highlight on mouse over
                                            property bool shouldBeHighlightedWhileRunning: false  // distinguish actions picked out for the batch run
                                            property int buttonIndex: index  // TODO: was -1
                                            Component.onCompleted: {
                                                // buttonIndex = index;
                                                background.border.color = 'dimgray';
                                            }
                                            display: model.icon ? AbstractButton.IconOnly : AbstractButton.TextOnly
                                            icon.source: model.icon || ''
                                            ToolTip {
                                                visible: mouseArea.containsMouse
                                                Component.onCompleted: {
                                                    text = '';
                                                    if (model.icon) {
                                                        text += model.name;
                                                    }
                                                    if (model.tooltip) {
                                                        text += text ? `<br>${model.tooltip}` : model.tooltip;
                                                    }
                                                    if (!model.icon && !model.tooltip) {
                                                        this.destroy();  // TODO: Loader?
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
                                                onStarted: stateCachedChanged()
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
                                                        // Erase highlighting if this action is the last in the series (or an error occurred)
                                                        if ((project.currentAction === model.action || !project.lastActionSucceed) &&
                                                            shouldBeHighlightedWhileRunning &&
                                                            (buttonIndex === (projActionsModel.count - 1) ||
                                                                !projActionsRow.children[buttonIndex + 1].shouldBeHighlightedWhileRunning)
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
                                                Detect modifier keys using overlaying MouseArea:
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
                                                function onActionFinished(action, success) {
                                                    if (action === model.action && settings.get('notifications') && !mainWindow.active) {
                                                        sysTrayIcon.showMessage(
                                                            success ? 'Success' : 'Error',  // title
                                                            `${project.name} - ${model.name}`,  // text
                                                            success ? Labs.SystemTrayIcon.Information : Labs.SystemTrayIcon.Warning,  // icon
                                                            5000  // ms
                                                        );
                                                    }
                                                }
                                            }
                                            /*
                                                "Blinky" glowing
                                            */
                                            RectangularGlow {
                                                id: glow
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
                                                        duration: 500
                                                    }
                                                    OpacityAnimator {
                                                        target: glow
                                                        from: 1
                                                        to: 0
                                                        duration: 500
                                                    }
                                                }
                                                DSM.StateMachine {
                                                    running: true
                                                    initialState: glowOff
                                                    DSM.State {
                                                        id: glowOff
                                                        onEntered: glow.visible = false
                                                        DSM.SignalTransition {
                                                            targetState: glowSuccess
                                                            signal: project.actionFinished
                                                            guard: action === model.action && success
                                                        }
                                                        DSM.SignalTransition {
                                                            targetState: glowError
                                                            signal: project.actionFinished
                                                            guard: action === model.action && !success
                                                        }
                                                    }
                                                    DSM.State {
                                                        id: glowOn
                                                        onEntered: glow.visible = true
                                                        DSM.SignalTransition {
                                                            targetState: glowOff
                                                            signal: glow.visibleChanged
                                                            guard: visible === false
                                                        }
                                                        DSM.SignalTransition {
                                                            targetState: glowOff
                                                            signal: project.actionStarted
                                                        }
                                                        DSM.State {
                                                            id: glowSuccess
                                                            onEntered: glow.color = 'lightgreen'
                                                        }
                                                        DSM.State {
                                                            id: glowError
                                                            onEntered: glow.color = 'lightcoral'
                                                        }
                                                    }
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
                        }
                    }
                }
            }
        }
    }

    /*
       Improvised status bar - simple text line. Currently, doesn't support smart intrinsic properties
       of a fully-fledged status bar, but is used only for a single feature so not a big deal right now
    */
    footer: Text {
        id: statusBar
        padding: 10
    }
}
