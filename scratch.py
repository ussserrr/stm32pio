# Second approach
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.rootContext().setContextProperty('projectsModel', projects)
view.setSource(QUrl('main.qml'))
