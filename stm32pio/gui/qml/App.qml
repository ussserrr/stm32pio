import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQml.Models 2.14
import QtQuick.Layouts 1.14
import QtGraphicalEffects 1.14
import QtQuick.Dialogs 1.3 as Dialogs
import QtQml.StateMachine 1.14 as DSM

import Qt.labs.platform 1.1 as Labs

// import Settings 1.0


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
    }

    // readonly property Settings settings: appSettings
    SettingsDialog {
        id: settingsDialog
    }

    /*
       The project visual representation is, in fact, split in two main parts: one in a list and one is
       an actual workspace. To avoid some possible bloopers we should make sure that both of them are loaded
       (at least at the subsistence level) before performing any actions with the project. To not reveal these
       QML-side implementation details to the backend we define this helper function that counts and stores
       a number of widgets currently loaded for each project in model and informs the Qt-side right after all
       necessary components become ready.
    */
    readonly property var componentsToWait: [
        'listElementProjectName',
        // 'listElementCurrentStage',
        'listElementBusyIndicator',
        // 'workspace'
    ]
    readonly property var initInfo: ({})
    function registerAsReady(projectIndex, component) {
        if (componentsToWait.includes(component)) {
            if (projectIndex in initInfo) {
                initInfo[projectIndex]++;
            } else {
                initInfo[projectIndex] = 1;
            }
            if (initInfo[projectIndex] === componentsToWait.length) {
                const indexInModel = projectsModel.index(projectIndex, 0);
                const project = projectsModel.data(indexInModel);
                project.qmlLoaded();
                delete initInfo[projectIndex];  // index can be reused
            }
        } else if (!component) {
            console.warn('Loaded component should identify itself. The call stack:', new Error().stack);
        } else if (!componentsToWait.includes(component)) {
            console.warn('Unrecognized loaded component:', component);
        }
    }

    Connections {
        target: projectsModel
        function onGoToProject(indexToGo) {
            projectsListView.currentIndex = indexToGo;
        }
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
        visible: settings === null ? false : settings.get('notifications')
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

        ListView {
            id: projectsListView

            Layout.preferredWidth: 2.6 * parent.width / 12  // ~1/5, probably should reduce or at least cast to the fraction of 10
            Layout.fillHeight: true
            clip: true
            // keyNavigationWraps: true

            highlight: Rectangle { color: 'darkseagreen' }
            highlightMoveDuration: 0  // turn off animations
            highlightMoveVelocity: -1

            model: DelegateModel {
                /*
                    Use DelegateModel as it has a feature to always preserve specified list items in memory so we can store an actual state
                    directly in the delegate
                */
                model: projectsModel  // backend-side
                // Loader for: DelegateModel.inPersistedItems and correct mouse click index change
                delegate: Loader {
                    sourceComponent: ProjectsListItem {}
                    onLoaded: DelegateModel.inPersistedItems = 1  // TODO: = true (5.15)
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
                        display: AbstractButton.TextBesideIcon
                        icon.source: '../icons/add.svg'
                        onClicked: addProjectFolderDialog.open()
                        ToolTip.visible: projectsListView.count === 0  // show when there is no items in the list
                        ToolTip.text: "<b>Hint:</b> add your project using this button or drag'n'drop it into the window"
                    }
                    Button {
                        text: 'Remove'
                        visible: projectsListView.currentIndex !== -1  // show only if any item is selected
                        display: AbstractButton.TextBesideIcon
                        icon.source: '../icons/remove.svg'
                        onClicked: {
                            const indexToRemove = projectsListView.currentIndex;
                            indexToRemove === 0 ? projectsListView.incrementCurrentIndex() : projectsListView.decrementCurrentIndex();
                            projectsModel.removeProject(indexToRemove);
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
                delegate: StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    function handleState() {
                        if (mainWindow.active &&  // the app got foreground
                            index === projectsWorkspaceView.currentIndex &&  // only for the current list item
                            !project.currentAction
                        ) {
                            project.updateState();
                        }
                    }
                    Component.onCompleted: {
                        // Several events lead to a single handler
                        projectsWorkspaceView.currentIndexChanged.connect(handleState);  // the project was selected in the list
                        mainWindow.activeChanged.connect(handleState);  // the app window has got (or lost, filter in the handler) the focus
                    }

                    readonly property int loaderIndex: 0
                    readonly property int initScreenIndex: 1
                    readonly property int workspaceIndex: 2
                    DSM.StateMachine {
                        running: true
                        initialState: workspace_loading
                        onStarted: {
                            if (!project.state.LOADING) {
                                project.currentStageChanged();
                            }
                        }
                        DSM.State {
                            id: workspace_loading
                            onEntered: workspaceLoader.active = true
                            DSM.SignalTransition {
                                targetState: workspace_emptyProject
                                signal: project.currentStageChanged
                                guard: project.currentStage === 'EMPTY' && !project.state.LOADING
                            }
                            DSM.SignalTransition {
                                targetState: workspace_main
                                signal: project.currentStageChanged
                                guard: project.currentStage !== 'EMPTY' && !project.state.LOADING
                            }
                            onExited: workspaceLoader.sourceComponent = undefined
                        }
                        DSM.State {
                            id: workspace_emptyProject
                            onEntered: currentIndex = initScreenIndex
                            DSM.SignalTransition {
                                targetState: workspace_main
                                signal: project.stateChanged
                                guard: project.currentStage !== 'EMPTY'
                            }
                        }
                        DSM.State {
                            id: workspace_main
                            onEntered: currentIndex = workspaceIndex
                            DSM.SignalTransition {
                                targetState: workspace_emptyProject
                                signal: project.stateChanged
                                guard: project.currentStage === 'EMPTY'
                            }
                        }
                    }

                    Loader {
                        id: workspaceLoader
                        sourceComponent: Item {
                            BusyIndicator {
                                anchors.centerIn: parent
                            }
                        }
                    }

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
                            // KeyNavigation.tab: runCheckBox  // not working...
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
                                        for (let i = projectActionsModel.statefulActionsStartIndex; i < projectActionsModel.count; ++i) {
                                            actions.push(`<b>${projectActionsModel.get(i).name}</b>`);
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
                                    for (let i = projectActionsModel.statefulActionsStartIndex + 1; i < projectActionsModel.count; ++i) {
                                        project.run(projectActionsModel.get(i).action, []);
                                    }
                                }

                                if (openEditor.checked) {
                                    project.run('start_editor', [settings.get('editor')]);
                                }

                                const config = project.config;
                                if (Object.keys(config['project']).length && !config['project']['board']) {
                                    // TODO: stm32pio.ini is hard-coded here though it is a parameter (settings.py)
                                    project.logAdded('WARNING  STM32 PlatformIO board is not specified, it will be needed on PlatformIO ' +
                                                    'project creation. You can set it in "stm32pio.ini" file in the project directory',
                                                    Logging.WARNING);
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        /*
                            Show this or action buttons
                        */
                        Text {
                            visible: project.state.EMPTY ? false : true
                            padding: 10
                            text: "<b>Project not found or no STM32CubeMX .ioc file is present</b>"
                            color: 'indianred'
                        }

                        /*
                            The core widget - a group of buttons mapping all main actions that can be performed on the given project.
                            They also serve the project state displaying - each button indicates a stage associated with it:
                                - green (and green glow): done
                                - yellow: in progress right now
                                - red glow: an error has occurred during the last execution
                        */
                        RowLayout {
                            id: projActionsRow
                            visible: project.state.EMPTY ? true : false
                            Layout.fillWidth: true
                            Layout.bottomMargin: 7
                            z: 1  // for the glowing animation
                            Repeater {
                                model: ProjectActionsModel {
                                    id: projectActionsModel
                                }
                                delegate: ActionButton {
                                    Layout.rightMargin: model.margin
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

    /*
       Improvised status bar - simple text line. Currently, doesn't support smart intrinsic properties
       of a fully-fledged status bar, but is used only for a single feature so not a big deal right now
    */
    footer: Text {
        id: statusBar
        padding: 10
    }
}
