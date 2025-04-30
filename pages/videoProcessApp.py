import sys
import cv2
import os
from PIL import Image
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

from pages.video import Ui_Form

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

class VideoApp(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(VideoApp, self).__init__()
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.setupUi(self)
        self.adjustUI()

    def adjustUI(self):
        self.cap = None
        self.total_frames = 0
        self.fps = 15

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        # play but
        self.setBut(self.playB, 'play')
        self.playB.setEnabled(False)
        self.playB.clicked.connect(self.play_pause_video)
        self.playing = False
        self.displayL.setText('')

        # connections
        self.browseB.clicked.connect(self.open_video)
        self.timeCtrl.sliderMoved.connect(self.slider_moved)
        self.applyB.clicked.connect(self.process_video)
        self.doneB.clicked.connect(self.close)

        #Progress
        self.progress.setValue(0)
        self.progress.setEnabled(False)

    def setBut(self, obj, icon):
        root, ext = os.path.splitext(icon)
        if ext == "":
            icon += '.png'
        elif ext == '.png':
            pass
        else:
            exit(10)
        icon_file = os.path.join(dir_path[:-6], 'icons', icon)
        obj.setText("")
        obj.setIcon(QtGui.QIcon(icon_file))


    def open_video(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Open Video File", filter="Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path == "":
            return
        self.pwd.setText(file_path)
        self.cap = cv2.VideoCapture(file_path)
        if self.cap.isOpened():
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

            self.timeCtrl.setMaximum(self.total_frames)
            self.timeCtrl.setEnabled(True)
            self.playB.setEnabled(True)
            self.setBut(self.playB, 'pause')

            self.playing = True
            self.timer.start(int(1000 / self.fps))

    def play_pause_video(self):
            if self.playing:
                self.playing = False
                self.timer.stop()
                self.setBut(self.playB, 'play')
            else:
                self.playing = True
                self.timer.start(int(1000 / self.fps))
                self.setBut(self.playB, 'pause')

    def next_frame(self):
        if self.cap.isOpened() and self.playing:
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
                current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.timeCtrl.blockSignals(True)
                self.timeCtrl.setValue(current_pos)
                self.timeCtrl.blockSignals(False)
            else:
                self.timer.stop()
                self.cap.release()
    
    def display_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        image = image.resize((400, 300))

        frame_array = np.array(image)
        height, width, channel = frame_array.shape
        bytes_per_line = 3 * width
        qimg = QImage(frame_array.data, width, height, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qimg)
        self.displayL.setPixmap(pixmap)

    def slider_moved(self, position):
        if self.cap:
            self.timer.stop()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
            if self.playing:
                self.timer.start(int(1000 / self.fps))

    def process_video(self):
        if self.pwd.toPlainText() == "":
            return
        self.cap = cv2.VideoCapture(self.pwd.toPlainText())

        # Get video properties
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        number_of_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Determine output filename
        base_name, ext = os.path.splitext(self.pwd.toPlainText())
        task =  0 
        if self.rotateC.isChecked():
            task += 1
        if self.leftC.isChecked():
            task += 2
        if self.rightC.isChecked(): 
            task += 4
        
        if task == 0:
            return
        self.progress.setEnabled(True)
        self.progress.setValue(0)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        pi = 0
        if task == 1:
            output_file = f"{base_name}_rotated.mp4"
            out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                out.write(frame)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out.release()
        elif task == 2:
            output_file = f"{base_name}_left.mp4"
            out = cv2.VideoWriter(output_file, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = frame[:, :width // 2]
                out.write(frame)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out.release()
        elif task == 3:
            output_file = f"{base_name}_rotated_left.mp4"
            out = cv2.VideoWriter(output_file, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                frame = frame[:, :width // 2]
                out.write(frame)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out.release()
        elif task == 4:
            output_file = f"{base_name}_right.mp4"
            out = cv2.VideoWriter(output_file, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = frame[:, width // 2:]
                out.write(frame)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out.release()
        elif task == 5:
            output_file = f"{base_name}_rotated_right.mp4"
            out = cv2.VideoWriter(output_file, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                frame = frame[:, width // 2:]
                out.write(frame)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out.release()
        elif task == 6:
            output_file_l = f"{base_name}_left.mp4"
            output_file_r = f"{base_name}_right.mp4"
            out_l = cv2.VideoWriter(output_file_l, fourcc, fps, (width//2, height))
            out_r = cv2.VideoWriter(output_file_r, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame_l = frame[:, :width // 2]
                frame_r = frame[:, width // 2:]
                out_l.write(frame_l), out_r.write(frame_r)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out_l.release(), out_r.release()
        elif task == 7:
            output_file_l = f"{base_name}_rotated_left.mp4"
            output_file_r = f"{base_name}_rotated_right.mp4"
            out_l = cv2.VideoWriter(output_file_l, fourcc, fps, (width//2, height))
            out_r = cv2.VideoWriter(output_file_r, fourcc, fps, (width//2, height))
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                frame_l = frame[:, :width // 2]
                frame_r = frame[:, width // 2:]
                out_l.write(frame_l), out_r.write(frame_r)
                pi += 1
                self.progress.setValue(int(pi / number_of_frames * 100))
            out_l.release(), out_r.release()

        self.progress.setValue(100)
        self.timer.stop()
        self.cap.release()
        self.playing = False

    def close(self):
        try:
            self.cap.release()
            self.playing = False
            self.timer.stop()
        except:
            pass
        super().close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoApp()
    window.show()
    sys.exit(app.exec_())
