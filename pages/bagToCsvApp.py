import sys
if sys.version_info < (3, 10):
    raise Exception("Python 3.10 or newer required")
import os
import json
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from pathlib import Path
from itertools import cycle
import multiprocessing as mp

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QObject, pyqtSlot, QUrl

from pages.bag_to_csv import Ui_Form




file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)
dir_path = os.path.dirname(dir_path)

def get_nested_attr(obj, attr_path, ignore_first=True):
    if obj is None:
        return globals()[attr_path]
    attrs = attr_path.split('.')
    if ignore_first:
        attrs = attrs[1:]
    for attr in attrs:
        obj = getattr(obj, attr)
        if obj is None:
            return None
    return obj

def gen_csv_task(args):
    worker_id, task, override_flag, typestore = args
    bag_name, bag_dir, target_dir, config, config_key = task

    FILE_NAME = os.path.join(target_dir, f"{bag_name}.{config_key}")
    BAG_NAME = os.path.join(bag_dir, bag_name)

    try:
        if os.path.getsize(FILE_NAME) > 0 and (not override_flag):
            return f"[Worker {worker_id}] Skipped {config_key} | {bag_name}"
    except:
        pass

    try:
        with open(FILE_NAME, 'w') as f, AnyReader([Path(BAG_NAME)], default_typestore=typestore) as reader:
            connections = [x for x in reader.connections if x.topic == config['topic']]
            if not connections:
                return f"[Worker {worker_id}] Failed {config_key} | {bag_name} (No topic match)"

            f.write('time,' + ','.join(config['cols']) + '\n')
            if "arrays" in config:
                for c, t, raw_msg in reader.messages(connections=connections):
                    msg = reader.deserialize(raw_msg, c.msgtype)
                    for attr in get_nested_attr(msg, config["arrays"]["field"]) or []:
                        row = [get_nested_attr(attr, fld) for fld in config["fields"]]
                        row.insert(0, t)
                        f.write(','.join(str(i) for i in row) + '\n')
            else:
                for c, t, raw_msg in reader.messages(connections=connections):
                    msg = reader.deserialize(raw_msg, c.msgtype)
                    row = [get_nested_attr(msg, fld) for fld in config["fields"]]
                    f.write(f'{t},' + ','.join(str(i) for i in row) + '\n')

        if os.path.getsize(FILE_NAME) > 0:
            return f"[Worker {worker_id}] Completed {config_key} | {bag_name}"
        else:
            os.remove(FILE_NAME)
            return f"[Worker {worker_id}] Failed {config_key} | {bag_name} (Empty)"
    except Exception as e:
        return f"[Worker {worker_id}] Error {config_key} | {bag_name}: {e}"



class BagToCsvApp(QtWidgets.QWidget, Ui_Form):
    default_config_path = os.path.join(dir_path, 'config.json')
    typestore = get_typestore(Stores.ROS1_NOETIC)
    def __init__(self, parent=None):
        super(BagToCsvApp, self).__init__(parent)
        self.setupUi(self)
        self.adjustUI()
        self.WARN_BAG = True
        self.WARN_CONFIG = True
        self.check_config()

    def adjustUI(self):
        self.override.setChecked(True)
        self.progressBar.setValue(0)
        self.progressBar.setEnabled(False)
        self.config.addItem(self.default_config_path)
        self.processors.setMaximum(mp.cpu_count())
        self.processors.setValue(mp.cpu_count())

        self.openBagB.clicked.connect(self.open_bags)
        self.openConfB.clicked.connect(self.open_config)
        self.closeB.clicked.connect(self.process)
        self.closeB.setText('Process')
        self.closeB.setEnabled(False)

        self.check_config()
    
    def open_bags(self):
        self.bagList.clear()
        file_path, _ = QFileDialog.getOpenFileNames(self, 'Open bag files', filter='*.bag')
        self.bagList.addItems(file_path)
        self.DIR = os.path.dirname(file_path[0])
        self.closeB.setEnabled(True)
        self.closeB.setText('Process')

    def open_config(self):
        self.config.clear()
        config_file = QFileDialog.getOpenFileName(self, 'Open config file', filter='*.json')[0]
        self.config.addItem(config_file)
        self.check_config()
        if self.cfg is not None:
            self.closeB.setEnabled(True)
            self.closeB.setText('Process')
        else:
            self.closeB.setEnabled(False)
            self.showWarning("Invalid config file", True)
    
    def showWarning(self, message, warn=True):
        if warn:
            msg = QMessageBox()
            msg.setWindowTitle("Bad Argument")
            msg.setText(message)
            msg.setIcon(QMessageBox.Critical)
            chk = QtWidgets.QCheckBox()
            chk.setText("Do show this again")
            msg.setCheckBox(chk)
            msg.exec_()
            if chk.isChecked():
                return False
        return True
    
    def check_config(self):
        try:
            with open(self.config.item(0).text()) as json_data_file:
                self.cfg = json.load(json_data_file)
        except:
            self.cfg = None

    def process(self):
        if self.bagList.count() == 0:
            self.WARN_BAG = self.showWarning("No bag files selected", self.WARN_BAG)
            return
        if self.cfg is None:
            self.WARN_CONFIG = self.showWarning("No config file selected", self.WARN_CONFIG)
            return

        self.reportList.clear()
        self.progressBar.setValue(0)
        self.progressBar.setEnabled(True)
        self.closeB.setEnabled(False)

        if not os.path.exists(os.path.join(self.DIR, 'csv')):
            os.makedirs(os.path.join(self.DIR, 'csv'))
        TARGET_DIR = os.path.join(self.DIR, 'csv')
        self.reportList.addItem(f"Using bag folder: {self.DIR}")
        self.reportList.addItem(f"Using target directory: {TARGET_DIR}")

        bag_list = [self.bagList.item(i).text() for i in range(self.bagList.count())]
        bag_list = [os.path.basename(bag) for bag in bag_list]
        tasks = []
        for bag_name in bag_list:
            for config_key in self.cfg:
                tasks.append((bag_name, self.DIR, TARGET_DIR, self.cfg[config_key], config_key))

        self.reportList.addItem(f"Number of tasks: {len(tasks)}")

        total_tasks = len(tasks)
        self.progressBar.setMaximum(total_tasks)

        task_queue = [
            (worker_id, task, self.override.isChecked(), self.typestore)
            for worker_id, task in zip(cycle(range(self.processors.value())), tasks)
        ]

        with mp.Pool(self.processors.value()) as pool:
            for i, result in enumerate(pool.imap_unordered(gen_csv_task, task_queue), 1):
                if result:
                    self.reportList.addItem(result)
                self.progressBar.setValue(i)

        self.reportList.addItem("All tasks completed.")
        self.closeB.setEnabled(True)



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = BagToCsvApp()
    window.show()
    sys.exit(app.exec_())