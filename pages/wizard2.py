# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './pages/UIs/wizard2.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Wiz_2(object):
    def setupUi(self, Wiz_2):
        Wiz_2.setObjectName("Wiz_2")
        Wiz_2.resize(493, 330)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(Wiz_2)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label = QtWidgets.QLabel(Wiz_2)
        self.label.setObjectName("label")
        self.verticalLayout_2.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.topiclist = QtWidgets.QListWidget(Wiz_2)
        self.topiclist.setDragEnabled(False)
        self.topiclist.setObjectName("topiclist")
        self.horizontalLayout.addWidget(self.topiclist)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        spacerItem = QtWidgets.QSpacerItem(20, 108, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.previousB = QtWidgets.QPushButton(Wiz_2)
        self.previousB.setObjectName("previousB")
        self.verticalLayout.addWidget(self.previousB)
        self.nextB = QtWidgets.QPushButton(Wiz_2)
        self.nextB.setObjectName("nextB")
        self.verticalLayout.addWidget(self.nextB)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.retranslateUi(Wiz_2)
        QtCore.QMetaObject.connectSlotsByName(Wiz_2)

    def retranslateUi(self, Wiz_2):
        _translate = QtCore.QCoreApplication.translate
        Wiz_2.setWindowTitle(_translate("Wiz_2", "Create *.DADS File Wizard (2/x)"))
        self.label.setText(_translate("Wiz_2", "Select topic(s)"))
        self.topiclist.setSortingEnabled(False)
        self.previousB.setText(_translate("Wiz_2", "Previous"))
        self.nextB.setText(_translate("Wiz_2", "Next"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Wiz_2 = QtWidgets.QWidget()
    ui = Ui_Wiz_2()
    ui.setupUi(Wiz_2)
    Wiz_2.show()
    sys.exit(app.exec_())
