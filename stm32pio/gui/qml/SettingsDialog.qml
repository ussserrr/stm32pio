/**
 * Slightly customized QSettings
 */

import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQuick.Layouts 1.14
import QtQuick.Dialogs 1.3 as Dialogs

import Settings 1.0


Dialogs.Dialog {
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
        Column {
            Layout.preferredWidth: 250
            CheckBox {
                id: notifications
                leftPadding: -3
            }
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                color: 'dimgray'
                text: "Get messages about completed project actions when the app is in the background"
            }
        }

        Text {
            Layout.columnSpan: 2
            Layout.maximumWidth: 250
            topPadding: 30
            bottomPadding: 10
            wrapMode: Text.Wrap
            text: `To clear <b>ALL</b> app settings including <b>the list of
                   added projects</b> click "Reset" then restart the app`
        }
    }
    // Set UI values there so they are always reflect the actual parameters
    // TODO: maybe map the data to the corresponding widgets automatically
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
