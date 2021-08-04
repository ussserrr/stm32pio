// Implicit references:
// project, index, projectsListView, registerAsReady

import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQuick.Layouts 1.14
import QtQml.StateMachine 1.14 as DSM

import ProjectListItem 1.0


RowLayout {
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
            font.weight: Font.Bold
            text: project.name
            DSM.StateMachine {
                running: true
                initialState: projectName_normal
                onStarted: registerAsReady(index, 'listElementProjectName')
                DSM.State {
                    id: projectName_normal
                    onEntered: projectName.color = 'black'
                    DSM.SignalTransition {
                        targetState: projectName_added
                        signal: project.initialized
                        guard: !project.fromStartup && projectsListView.currentIndex !== index
                    }
                    DSM.SignalTransition {
                        targetState: projectName_error
                        signal: project.stateChanged
                        guard: !project.state.EMPTY && !project.state.LOADING
                    }
                }
                DSM.State {
                    id: projectName_added
                    onEntered: projectName.color = 'seagreen'
                    DSM.SignalTransition {
                        targetState: projectName_normal
                        signal: projectsListView.currentIndexChanged
                        guard: projectsListView.currentIndex === index && project.state.EMPTY
                    }
                    DSM.SignalTransition {
                        targetState: projectName_error
                        signal: projectsListView.currentIndexChanged
                        guard: projectsListView.currentIndex === index && !project.state.EMPTY
                    }
                }
                DSM.State {
                    id: projectName_error
                    onEntered: projectName.color = 'indianred'
                    DSM.SignalTransition {
                        targetState: projectName_normal
                        signal: project.stateChanged
                        guard: project.state.EMPTY
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
            text: ProjectStage[project.currentStage]
            DSM.StateMachine {
                running: true
                initialState: projectsListView.currentIndex === index
                    ? projectCurrentStage_navigated
                    : projectCurrentStage_inactive
                DSM.State {
                    id: projectCurrentStage_navigated
                    initialState: (project.state.EMPTY || project.state.LOADING)
                        ? projectCurrentStage_navigatedNormal
                        : projectCurrentStage_navigatedError
                    DSM.State {
                        id: projectCurrentStage_navigatedNormal
                        onEntered: projectCurrentStage.color = 'black'
                        DSM.SignalTransition {
                            targetState: projectCurrentStage_navigatedError
                            signal: project.stateChanged
                            guard: !project.state.EMPTY
                        }
                    }
                    DSM.State {
                        id: projectCurrentStage_navigatedError
                        onEntered: projectCurrentStage.color = 'indianred'
                        DSM.SignalTransition {
                            targetState: projectCurrentStage_navigatedNormal
                            signal: project.stateChanged
                            guard: project.state.EMPTY
                        }
                    }
                    DSM.SignalTransition {
                        targetState: projectCurrentStage_inactive
                        signal: projectsListView.currentIndexChanged
                        guard: projectsListView.currentIndex !== index
                    }
                }
                DSM.State {
                    id: projectCurrentStage_inactive
                    initialState: (project.state.EMPTY || project.state.LOADING)
                        ? projectCurrentStage_inactiveNormal
                        : projectCurrentStage_inactiveError
                    DSM.State {
                        id: projectCurrentStage_inactiveNormal
                        onEntered: projectCurrentStage.color = 'darkgray'
                        DSM.SignalTransition {
                            targetState: projectCurrentStage_inactiveError
                            signal: project.stateChanged
                            guard: !project.state.EMPTY
                        }
                        DSM.SignalTransition {
                            targetState: projectCurrentStage_inactiveAdded
                            signal: project.initialized
                            guard: project.state.EMPTY && !project.fromStartup
                        }
                    }
                    DSM.State {
                        id: projectCurrentStage_inactiveError
                        onEntered: projectCurrentStage.color = 'indianred'
                        DSM.SignalTransition {
                            targetState: projectCurrentStage_inactiveNormal
                            signal: project.stateChanged
                            guard: project.state.EMPTY
                        }
                    }
                    DSM.State {
                        id: projectCurrentStage_inactiveAdded
                        onEntered: projectCurrentStage.color = 'seagreen'
                    }
                    DSM.SignalTransition {
                        targetState: projectCurrentStage_navigated
                        signal: projectsListView.currentIndexChanged
                        guard: projectsListView.currentIndex === index
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
            onStarted: registerAsReady(index, 'listElementBusyIndicator')
            DSM.State {
                id: normal
                onEntered: actionIndicator.visible = false
                DSM.SignalTransition {
                    targetState: busy
                    signal: project.actionStarted
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
                    signal: project.initialized
                }
                DSM.SignalTransition {
                    targetState: normal
                    signal: project.actionFinished
                    guard: projectsListView.currentIndex === index
                }
                DSM.SignalTransition {
                    targetState: indication
                    signal: project.actionFinished
                }
            }
            DSM.State {
                id: indication
                onEntered: {
                    lastActionNotification.color = project.lastActionSucceed ? 'lightgreen' : 'lightcoral';
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
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Rectangle {  // Circle :)
                id: lastActionNotification
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
        onClicked: projectsListView.currentIndex = index
    }
}
