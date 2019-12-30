import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12

// import ProjectListItem 1.0

ApplicationWindow {
    visible: true
    width: 640
    height: 480
    title: qsTr("PyQt5 love QML")
    color: "whitesmoke"

    GridLayout {
        columns: 2
        rows: 1
        // width: 200; height: 250

        ListView {
            width: 200; height: 250
            // anchors.fill: parent
            model: projectsModel
            delegate: Item {
                id: projectListItem
                width: ListView.view.width
                height: 40
                // property ProjectListItem listItem: projectsModel.getProject(index)
                Column {
                    // Text { text: listItem.name }
                    Text { text: '<b>Name:</b> ' + display.name }
                    Text { text: '<b>State:</b> ' + display.state }
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        projectListItem.ListView.view.currentIndex = index;
                        view2.currentIndex = index
                    }
                }
            }
            highlight: Rectangle { color: "lightsteelblue"; radius: 5 }
            // focus: true
        }

        SwipeView {
            id: view2
            width: 200; height: 250
            // anchors.fill: parent
            Repeater {
                model: projectsModel
                Column {
                    Button {
                        text: 'Click me'
                        onClicked: {
                            // console.log('here')
                            projectsModel.run(index, 'clean')
                        }
                    }
                    ScrollView {
                        height: 100
                        TextArea {
                            id: log
                            //anchors.centerIn: parent
                            text: 'Initial log content'
                        }
                    }
                    Text {
                        //anchors.centerIn: parent
                        text: '<b>Name:</b> ' + display.name
                    }
                }
            }
        }
    }

}
