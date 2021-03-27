// implicit ones:
// index, model, project (+ mainWindow, settings, sysTrayIcon)

import QtQuick 2.14
import QtQuick.Controls 2.14
import QtGraphicalEffects 1.14
import QtQml.StateMachine 1.14 as DSM

import Qt.labs.platform 1.1 as Labs


Button {
    property var thisButton: model
    text: thisButton.name
    property bool shouldBeHighlighted: false  // highlight on mouse over
    property bool shouldBeHighlightedWhileRunning: false  // distinguish actions picked out for the batch run
    property int thisButtonIndex: index  // TODO: was -1
    Component.onCompleted: {
        // thisButtonIndex = index;
        background.border.color = 'dimgray';
    }
    display: thisButton.icon ? AbstractButton.IconOnly : AbstractButton.TextOnly
    icon.source: thisButton.icon || ''
    ToolTip {
        visible: mouseArea.containsMouse
        Component.onCompleted: {
            if (thisButton.icon || thisButton.tooltip) {
                let content = '';
                if (thisButton.icon) {
                    content += thisButton.name;
                }
                if (thisButton.tooltip) {
                    content += content ? `<br>${thisButton.tooltip}` : thisButton.tooltip;
                }
                text = content;
            } else {
                this.destroy();
            }
        }
    }
    onClicked: {
        // JS array cannot be attached to a ListElement (at least in a non-hacky manner) so we fill arguments here
        const args = [];
        switch (thisButton.action) {
            case 'start_editor':
                args.push(settings.get('editor'));
                break;
            case 'clean':
                log.clear();
                break;
            default:
                break;
        }
        project.run(thisButton.action, args);
    }
    /*
        As the button reflects relatively complex logic it's easier to maintain using the state machine technique.
        We define states and allowed transitions between them, all other stuff is managed by the DSM framework.
        You can find the graphical diagram somewhere in the docs
    */
    DSM.StateMachine {
        initialState: main  // start position
        running: true  // run immediately
        onStarted: {
            if (!project.state.LOADING) {
                project.stateChanged();
            }
        }
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
                    signal: project.stateChanged
                    guard: project.state[thisButton.stageRepresented] ? true : false  // explicitly convert to boolean
                }
                onEntered: {
                    palette.button = 'lightgray';
                }
            }
            DSM.State {
                id: stageFulfilled
                DSM.SignalTransition {
                    targetState: normal
                    signal: project.stateChanged
                    guard: project.state[thisButton.stageRepresented] ? false : true
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
                if (project.currentAction === thisButton.action) {
                    palette.button = 'gold';
                }
                if (shouldBeHighlightedWhileRunning) {
                    background.border.width = 2;
                }
            }
            onExited: {
                // Erase highlighting if this action is the last in the series (or an error occurred)
                if ((project.currentAction === thisButton.action || !project.lastActionSucceed) &&
                    shouldBeHighlightedWhileRunning &&
                    (thisButtonIndex === (projectActionsModel.count - 1) ||
                        !projActionsRow.children[thisButtonIndex + 1].shouldBeHighlightedWhileRunning)
                ) {
                    for (let i = projectActionsModel.statefulActionsStartIndex; i <= thisButtonIndex; ++i) {
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
            for (let i = projectActionsModel.statefulActionsStartIndex; i <= thisButtonIndex; ++i) {
                projActionsRow.children[i].shouldBeHighlighted = shiftPressed;
            }
        }
        onClicked: {
            if (shiftPressed && thisButtonIndex >= projectActionsModel.statefulActionsStartIndex) {
                for (let i = projectActionsModel.statefulActionsStartIndex; i <= thisButtonIndex; ++i) {
                    projActionsRow.children[i].shouldBeHighlighted = false;
                    projActionsRow.children[i].shouldBeHighlightedWhileRunning = true;
                }
                for (let i = projectActionsModel.statefulActionsStartIndex; i < thisButtonIndex; ++i) {
                    project.run(projectActionsModel.get(i).action, []);
                }
            }
            parent.clicked();  // pass the event to the underlying button though all work can be done in-place
            if (ctrlPressed && thisButton.action !== 'start_editor') {
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
            if (thisButton.action !== 'start_editor') {
                let preparedText = `<b>Ctrl</b>-click to open the editor specified in the <b>Settings</b>
                                    after the operation`;
                if (thisButtonIndex >= projectActionsModel.statefulActionsStartIndex) {
                    preparedText += `, <b>Shift</b>-click to perform all actions prior this one (including).
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
            if (action === thisButton.action && settings.get('notifications') && !mainWindow.active) {
                sysTrayIcon.showMessage(
                    success ? 'Success' : 'Error',  // title
                    `${project.name} - ${thisButton.name}`,  // text
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
                    guard: action === thisButton.action && success
                }
                DSM.SignalTransition {
                    targetState: glowError
                    signal: project.actionFinished
                    guard: action === thisButton.action && !success
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