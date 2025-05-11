from PyQt5 import QtCore, QtGui, QtWidgets
from pages.about import Ui_Form
import os

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)
dir_path = os.path.dirname(dir_path)
logo_path = os.path.join(dir_path, 'icons', 'logo.png')
class aboutPage(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(aboutPage, self).__init__()
        self.setupUi(self)
        self.label.setPixmap(QtGui.QPixmap(logo_path))
