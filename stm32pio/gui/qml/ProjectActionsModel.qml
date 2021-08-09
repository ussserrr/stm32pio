import QtQuick 2.14


ListModel {
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
        action: 'save_config'
        stageRepresented: 'INITIALIZED'  // the project stage this button is representing
        // TODO: stm32pio.ini is hard-coded here though it is a parameter (settings.py)
        tooltip: "Saves the current configuration to the config file <b>stm32pio.ini</b>"
    }
    ListElement {
        name: 'Generate'
        action: 'generate_code'
        stageRepresented: 'GENERATED'
    }
    ListElement {
        name: 'Init PlatformIO'
        action: 'pio_init'
        stageRepresented: 'PIO_INITIALIZED'
    }
    ListElement {
        name: 'Patch'
        action: 'patch'
        stageRepresented: 'PATCHED'
    }
    ListElement {
        name: 'Build'
        action: 'build'
        stageRepresented: 'BUILT'
    }
}
