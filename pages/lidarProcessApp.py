import sys
import os
import numpy as np
import json
import pandas as pd

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
     QFileDialog, QListWidgetItem
)
from PyQt5.QtCore import Qt
from pages.lidar_process import Ui_Form

class lidarProcessApp(QtWidgets.QWidget, Ui_Form):
    def __init__(self, extern=None):
        super(lidarProcessApp, self).__init__()
        self.setupUi(self)
        self.extern = extern
        self.adjustUI()

    def adjustUI(self):
        self.browseB.clicked.connect(self.open_dads)
        self.csvList.itemClicked.connect(self.handle_item_click)
        self.applyB.clicked.connect(self.cleanUp)

        self.progressBar.setValue(0)
        self.progressBar.setEnabled(False)
        self.report.setText('')

    def add_item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.csvList.addItem(item)
            

    def open_dads(self):
        self.main_dict = {}
        self.csvList.clear()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open DADS File', filter='Trip Files (*.DADS)'
        )
        self.dads_pwd.clear()
        self.dads_pwd.addItem(file_path)
        try:
            with open(file_path, 'r') as f:
                self.main_dict = json.load(f)
        except:
            self.main_dict = {}
            return
        self.add_item('Select All')
        self.add_item('Deselect All')
        for file in self.main_dict['topics']['lidarObj']:
            self.add_item(file)

    def handle_item_click(self, item):
        if item.text() == 'Select All':
            for i in range(self.csvList.count()):
                self.csvList.item(i).setCheckState(Qt.Checked)
        elif item.text() == 'Deselect All':
            for i in range(self.csvList.count()):
                self.csvList.item(i).setCheckState(Qt.Unchecked)

    def get_checked_items(self):
        checked = []
        for i in range(2, self.csvList.count()):
            item = self.csvList.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked
    
    def cleanUp(self):
        self.report.setText('Task 1/3: Cleaning CSV files...')
        checked = self.get_checked_items()
        if not checked:
            return
        dir_name = os.path.dirname(self.dads_pwd.item(0).text())
        file_name = os.path.join(checked[0]+'.lidar')
        self.progressBar.setMaximum(len(checked))
        self.progressBar.setEnabled(True)
        self.progressBar.setValue(0)
        data_list = []
        idx = 0
        max = 0
        for file in checked:
            idx += 1
            self.progressBar.setValue(idx)
            file_path = os.path.join(dir_name, 'csv', file + '.lidarObj')
            data = pd.read_csv(file_path)
            data = data.dropna()
            data = data.reset_index(drop=True)
            data_list.append(data)
            max += len(data)
        self.report.setText('Task 2/3: Loading CSV files...')
        self.progressBar.setMaximum(max)
        self.progressBar.setValue(0)
        self.lidar = {}
        idx = 0
        for data in data_list:
            for i in range(len(data)):
                idx += 1
                self.progressBar.setValue(idx)
                label = str(data['label'][i])
                if 'car' in label:
                    label = 'car'
                elif 'bike' in label:
                    label = 'truck'
                elif 'pedestrian' in label:
                    label = 'pedestrian'
                else:
                    continue
                entry = (data.loc[i, 'x'], data.loc[i, 'y'], data.loc[i, 'z'], label)
                key = int(data.loc[i, 'time'])
                if data.loc[i, 'time'] not in self.lidar.keys():
                    self.lidar[key] = [entry]
                else:
                    self.lidar[key].append(entry)
        self.report.setText('Task 3/3: Saving as json...')
        with open(os.path.join(dir_name, file_name), 'w') as f:
            json.dump(self.lidar, f)
        self.main_dict['lidar'] = file_name
        self.extern_func()
        self.report.setText('Done!')

    def extern_func(self):
        if self.extern is None:
            return
        self.extern(self.main_dict)

                        

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = lidarProcessApp()
    window.show()
    sys.exit(app.exec_())