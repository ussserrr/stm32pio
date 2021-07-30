import QtQuick 2.14
import QtQuick.Controls 2.14


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
        /**
         * Trigger full run
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
