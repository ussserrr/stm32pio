import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQml.Models 2.14
import QtQuick.Layouts 1.14
import QtQuick.Dialogs 1.3 as Dialogs
import QtQml.StateMachine 1.14 as DSM

import Qt.labs.platform 1.1 as Labs


ApplicationWindow {
    id: mainWindow
    visible: true
    minimumWidth: 980  // comfortable initial size for all platforms (as the same style is used for any of them)
    minimumHeight: 310
    height: 310  // 530 TODO
    title: 'stm32pio'
    color: 'whitesmoke'

    /**
     * Notify the front about the end of an initial loading
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
        text: "There was an error during the initialization of Python backend. Please see terminal output for more details"
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

    AboutDialog { id: aboutDialog }

    SettingsDialog { id: settingsDialog }

    /**
     * The project visual representation is, in fact, split in two main parts: one in a list and one is
     * an actual workspace. To avoid some possible bloopers we should make sure that both of them are loaded
     * (at least at the core level) before performing any actions with the project. To not reveal these
     * QML-side implementation details to the backend we define this helper function that counts and stores
     * a number of widgets currently loaded for each project in model and informs the Qt-side right after all
     * necessary components become ready.
     */
    readonly property var componentsToWait: [
        'listElementProjectName',
        'listElementBusyIndicator'
    ]
    readonly property var progressPerProject: ({})
    function registerAsReady(projectIndex, component) {
        if (componentsToWait.includes(component)) {
            if (projectIndex in progressPerProject) {
                progressPerProject[projectIndex]++;
            } else {
                progressPerProject[projectIndex] = 1;
            }
            if (progressPerProject[projectIndex] === componentsToWait.length) {
                const indexInModel = projectsModel.index(projectIndex, 0);
                const project = projectsModel.data(indexInModel);
                project.qmlLoaded();
                delete progressPerProject[projectIndex];  // index can be reused
            }
        } else if (!component) {
            console.warn('Loaded component should identify itself. The call stack:', new Error().stack);
        } else if (!componentsToWait.includes(component)) {
            console.warn('Unrecognized loaded component:', component);
        }
    }

    menuBar: MenuBar {
        Menu {
            title: '&Menu'
            Action { text: '&Settings'; onTriggered: settingsDialog.open() }
            Action { text: '&About'; onTriggered: aboutDialog.open() }
            MenuSeparator {}
            // Use mainWindow.close() instead of Qt.quit() to prevent segfaults (messed up shutdown order)
            Action { text: '&Quit'; onTriggered: mainWindow.close() }
        }
    }

    Labs.SystemTrayIcon {
        id: sysTrayIcon
        icon.source: '../icons/icon.svg'
        visible: settings === null ? false : settings.get('notifications')
    }

    DropHereToAdd {}

    /**
     * All layouts and widgets try to be adaptive to variable parents, siblings, window and whatever else sizes
     * so we extensively use Grid, Column and Row layouts. The most high-level one is a composition of the list
     * and the workspace in two columns
     */
    GridLayout {
        anchors.fill: parent
        rows: 1
        z: 2  // do not clip glow animation (see below)

        ListView {
            id: projectsListView

            Layout.preferredWidth: 0.217 * parent.width
            Layout.fillHeight: true
            clip: true
            // keyNavigationWraps: true  // TODO

            highlight: Rectangle { color: 'darkseagreen' }
            highlightMoveDuration: 0  // turn off animations
            highlightMoveVelocity: -1

            Connections {
                target: projectsModel
                function onGoToProject(indexToGo) {
                    projectsListView.currentIndex = indexToGo;
                    projectsListView.positionViewAtIndex(indexToGo, ListView.Center);
                }
            }

            model: DelegateModel {
                /**
                 * Use DelegateModel as it has a feature to always preserve specified list items in memory
                 * so we can store an actual state directly in the delegate
                 */
                model: projectsModel  // backend-side
                // Here Loader is used for: DelegateModel.inPersistedItems and correct mouse click index change
                delegate: Loader {
                    sourceComponent: ProjectsListItem {}
                    onLoaded: DelegateModel.inPersistedItems = 1  // TODO: = true (only >5.15)
                }
            }

            Labs.FolderDialog {
                id: addProjectFolderDialog
                currentFolder: Labs.StandardPaths.standardLocations(Labs.StandardPaths.HomeLocation)[0]
                onAccepted: projectsModel.addProjectsByPaths([folder])
            }
            footerPositioning: ListView.OverlayFooter
            footer: ProjectsListFooter {}
        }


        /*
         * Main workspace. StackLayout's Repeater component seamlessly uses the same projects model (showing one -
         * current - project per screen) as for list so all data is synchronized without any additional effort
         */
        StackLayout {
            id: projectsWorkspaceView
            Layout.preferredWidth: parent.width - projectsListView.width
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
                    // Several events lead to a single handler
                    Component.onCompleted: {
                        // the project was selected in the list
                        projectsWorkspaceView.currentIndexChanged.connect(handleState);
                        // the app window has got (or lost, filter this case in the handler) the focus
                        mainWindow.activeChanged.connect(handleState);
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
                        sourceComponent: Item { BusyIndicator { anchors.centerIn: parent } }
                    }

                    InitScreen {}

                    ColumnLayout {
                        /**
                         * Show this or action buttons
                         */
                        Text {
                            visible: project.state.EMPTY ? false : true
                            padding: 10
                            text: "<b>Project not found or no STM32CubeMX .ioc file is present</b>"
                            color: 'indianred'
                        }

                        /*
                         * The core widget - a group of buttons mapping all main actions that can be performed on the given project.
                         * They also serve the project state displaying - each button indicates a stage associated with it:
                         *   - green (and green glow): done
                         *   - yellow: in progress right now
                         *   - red glow: an error has occurred during the last execution
                         */
                        RowLayout {
                            id: projActionsRow
                            visible: project.state.EMPTY ? true : false
                            Layout.fillWidth: true
                            Layout.bottomMargin: 7
                            z: 1  // for the glowing animation
                            Repeater {
                                model: ProjectActionsModel { id: projectActionsModel }
                                delegate: ActionButton {
                                    Layout.rightMargin: model.margin
                                }
                            }
                        }

                        LogArea {
                            id: log
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                        }
                    }
                }
            }
        }
    }

    /**
     * Improvised status bar - simple text line. Currently, doesn't support smart intrinsic properties
     * of a fully-fledged status bar, but is used only for a single feature so not a big deal right now
     */
    footer: Text {
        id: statusBar
        padding: 10
    }
}
