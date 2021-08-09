import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQuick.Layouts 1.14


Rectangle {  // Probably should use Pane but need to override default window color then
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
                projectsModel.removeRow(indexToRemove);
            }
        }
    }
}
