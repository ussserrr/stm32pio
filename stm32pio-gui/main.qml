import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12

//import ProjectListItem 1.0

ApplicationWindow {
    visible: true
    width: 640
    height: 480
    title: qsTr("PyQt5 love QML")
    color: "whitesmoke"

    GridLayout {
        id: mainGrid
        columns: 3
        rows: 1
        // width: 200; height: 250

        ListView {
            width: 200; height: 250
            // anchors.fill: parent
            model: projectsModel
            delegate: Item {
                id: projectListItem
                //property ProjectListItem listItem: projectsModel.getProject(index)
                width: ListView.view.width
                height: 40
                model: display
                // Column {
                //     //Text { text: '<b>Name:</b> ' + listItem.name }
                //     Text { text: '<b>Name:</b> ' + name }
                //     Text { text: '<b>State:</b> ' + state }
                // }
                // MouseArea {
                //     anchors.fill: parent
                //     onClicked: {
                //         projectListItem.ListView.view.currentIndex = index;
                //         view2.currentIndex = index
                //     }
                // }
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
                    id: 'col'
                    Button {
                        text: 'Click me'
                        onClicked: {
                            projectsModel.run(index, 'clean')
                            log.append('text text text')
                        }
                    }
                    ScrollView {
                        id: 'sv'
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

        Button {
            text: 'Global'
            onClicked: {
                view2.children[1].col.sv.log.append('text text text')
                projectsModel[1].append('text text text')
            }
        }
    }

    // Connections {
    //     target: projectsModel
    //     onLogAdded {
    //         log.append(message)
    //     }
    // }

}
