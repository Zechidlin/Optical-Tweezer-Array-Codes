from PyQt5.QtWidgets import QFrame,QCheckBox,QComboBox,QDialog,QApplication,QWidget,QLabel,QLineEdit,QPushButton,QVBoxLayout,QTextEdit,QHBoxLayout
import random
import threading
import spcm
from PyQt5.QtCore import QThread,pyqtSignal,pyqtSlot,Qt
from PyQt5.QtGui import QPixmap,QImage
import numpy as np
import os
import tifffile as tiff
from pylablib.devices import DCAM
from Imganalysis import greyintensity
import matplotlib.pyplot as plt
import sys
import re
import time
import traceback
import math
from vimba import *
import socket
import pickle
from PIL import Image

global nphotos,exptime,heading,imganalysis
global brightspots,darkspots,card_start

server_ip = '155.198.206.58'

card_start = False

global freqs,freqs_list,num_freq,freq_spacing,collective_amplitude,firstramp,amp_list

# A GUI for AWG and camera parameters input and control

def Gaussian(x,mean,var,A):
    return A*1/(math.sqrt(2*math.pi)*var)*math.exp((-1/2)*((x-mean)/var)**2)

def send_command(target_ip,command,num):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.connect((target_ip,12345))
        s.sendall(command.encode())

        received_data = b''
        while True:
            packet = s.recv(327680*num)
            if not packet:
                break
            received_data += packet
            break
        image = pickle.loads(received_data)
        print('Image received!')
            
        return pickle.loads(received_data)

## UI Generation
class UIDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AWG And Camera Control")
        self.setGeometry(300,400,1500,300)

        self.beginvalue = None
        self.iteration = None

        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)

        self.initUI()

    def initUI(self):


        generalUI = QVBoxLayout()

        layout = QHBoxLayout()

        left_layout = QVBoxLayout()

        self.text_panel = QTextEdit(self)
        self.text_panel.setReadOnly(True)
        layout.addWidget(self.text_panel)

        left_label = QLabel('Tweezer Control')
        left_layout.addWidget(left_label)

        self.central_freq_label = QLabel("Central Frequency / MHz")
        self.central_freq_input = QLineEdit(self)
        left_layout.addWidget(self.central_freq_label)
        left_layout.addWidget(self.central_freq_input)

        self.freq_spacing_label = QLabel("Spacing Between Frequencies / MHz")
        self.freq_spacing_input = QLineEdit(self)
        left_layout.addWidget(self.freq_spacing_label)
        left_layout.addWidget(self.freq_spacing_input)

        self.freq_number_label = QLabel("Number of Frequencies")
        self.freq_number_input = QLineEdit(self)
        left_layout.addWidget(self.freq_number_label)
        left_layout.addWidget(self.freq_number_input)

        self.collective_amplitude_label = QLabel("Collective Amplitude(0-1)")
        self.collective_amplitude_input = QLineEdit(self)
        left_layout.addWidget(self.collective_amplitude_label)
        left_layout.addWidget(self.collective_amplitude_input)

        self.freq_ramp_scope_label = QLabel("Frequency Ramp Slope / MHz/s")
        self.freq_ramp_scope_input = QLineEdit(self)
        left_layout.addWidget(self.freq_ramp_scope_label)
        left_layout.addWidget(self.freq_ramp_scope_input)
        self.freq_ramp_scope_input.setEnabled(False)
        
        self.amp_ramp_scope_label = QLabel("Amplitude Ramp Slope / 1/s")
        self.amp_ramp_scope_input = QLineEdit(self)
        left_layout.addWidget(self.amp_ramp_scope_label)
        left_layout.addWidget(self.amp_ramp_scope_input)
        self.amp_ramp_scope_input.setEnabled(False)

        self.ramp_time_label = QLabel("Ramp Time / s")
        self.ramp_time_input = QLineEdit(self)
        left_layout.addWidget(self.ramp_time_label)
        left_layout.addWidget(self.ramp_time_input)
        self.ramp_time_input.setEnabled(False)

        self.select_chirp_label = QLabel("Frequency to be chirped")
        self.select_chirp_input = QComboBox(self)
        left_layout.addWidget(self.select_chirp_label)
        left_layout.addWidget(self.select_chirp_input)
        self.select_chirp_input.setEnabled(False)
        
        self.ontweezer_label = QLabel("Unoccupied Frequencies")
        self.ontweezer_input = QLineEdit(self)
        left_layout.addWidget(self.ontweezer_label)
        left_layout.addWidget(self.ontweezer_input)
        self.ontweezer_input.setEnabled(False)

        self.default_button = QPushButton("Default Values")
        self.default_button.clicked.connect(self.default_tweezer)
        left_layout.addWidget(self.default_button)

        self.array_button = QPushButton("Generate Array")
        self.array_button.clicked.connect(self.array)
        left_layout.addWidget(self.array_button)
        

        self.update_button = QPushButton("Turn Off Unused Frequencies")
        self.update_button.clicked.connect(self.update)
        left_layout.addWidget(self.update_button)
        self.update_button.setEnabled(False)

        self.ramp_button = QPushButton("Linearly Ramp Amplitude and Frequency")
        self.ramp_button.clicked.connect(self.ramp)
        left_layout.addWidget(self.ramp_button)
        self.ramp_button.setEnabled(False)

        self.auto_button = QPushButton('Automatically Ramp Frequencies')
        self.auto_button.clicked.connect(self.auto)
        left_layout.addWidget(self.auto_button)
        self.auto_button.setEnabled(False)
        

        self.stop_button = QPushButton("Stop",self)
        self.stop_button.clicked.connect(self.stop)
        left_layout.addWidget(self.stop_button)
        self.stop_button.setEnabled(False)

        layout.addLayout(left_layout)


        right_layout = QVBoxLayout()

        right_label = QLabel('Camera Control')
        right_layout.addWidget(right_label)

        self.nphotos_label = QLabel("Number of Photos Taken / Experiment Iteration")
        self.nphotos_input = QLineEdit(self)
        right_layout.addWidget(self.nphotos_label)
        right_layout.addWidget(self.nphotos_input)

        self.exptime_label = QLabel("Exposure Time / us")
        self.exptime_input = QLineEdit(self)
        right_layout.addWidget(self.exptime_label)
        right_layout.addWidget(self.exptime_input)

        self.gain_label = QLabel("Gain / dB")
        self.gain_input = QLineEdit(self)
        right_layout.addWidget(self.gain_label)
        right_layout.addWidget(self.gain_input)

        self.heading_label = QLabel("Heading of Photos")
        self.heading_input = QLineEdit(self)
        right_layout.addWidget(self.heading_label)
        right_layout.addWidget(self.heading_input)


        imageprocesslayout = QHBoxLayout()

        imganalysislayout = QVBoxLayout()
        self.imganalysis_label = QLabel("Image Classification")
        self.imganalysis_input = QCheckBox(self)
        imganalysislayout.addWidget(self.imganalysis_label)
        imganalysislayout.addWidget(self.imganalysis_input)

        borderlinelayout = QVBoxLayout()
        self.borderline_label = QLabel("Add Borderlines")
        self.borderline_input = QCheckBox(self)
        borderlinelayout.addWidget(self.borderline_label)
        borderlinelayout.addWidget(self.borderline_input)

        analysislayout = QVBoxLayout()
        self.analysis_label = QLabel("Image Analysis")
        self.analysis_input = QCheckBox(self)
        analysislayout.addWidget(self.analysis_label)
        analysislayout.addWidget(self.analysis_input)

        croplayout = QVBoxLayout()
        self.crop_label = QLabel("Crop Images")
        self.crop_input = QCheckBox(self)
        croplayout.addWidget(self.crop_label)
        croplayout.addWidget(self.crop_input)

        imageprocesslayout.addLayout(imganalysislayout)
        imageprocesslayout.addLayout(borderlinelayout)
        imageprocesslayout.addLayout(analysislayout)
        imageprocesslayout.addLayout(croplayout)
        

        right_layout.addLayout(imageprocesslayout)

        camerabuttonslayout = QHBoxLayout()
        
        self.camerastart_button = QPushButton("Take Photos",self)
        camerabuttonslayout.addWidget(self.camerastart_button)
        self.camerastart_button.clicked.connect(self.CamStart)


        camrestart_button = QPushButton("Clear",self)
        camerabuttonslayout.addWidget(camrestart_button)
        camrestart_button.clicked.connect(self.Clear)

        default_button = QPushButton("Default Values",self)
        camerabuttonslayout.addWidget(default_button)
        default_button.clicked.connect(self.Default)

        right_layout.addLayout(camerabuttonslayout)



        photolayout = QVBoxLayout()
        photolabel = QLabel("Last Photo Taken")
        self.location = QLabel(self)
        self.photopanel = QLabel(self)
        self.photopanel.setPixmap(QPixmap(r"C:\Users\CaFMOT\Desktop\imgs\background.tif"))


        imglayout = QVBoxLayout()
        imglayout.addWidget(photolabel)
        imglayout.addWidget(self.location)
        imglayout.addWidget(self.photopanel)
        right_layout.addLayout(imglayout)

        explayout = QHBoxLayout()

        expstartbutton = QPushButton("Start Experiment")
        explayout.addWidget(expstartbutton)
        expstartbutton.clicked.connect(self.expStart)

        dpbutton = QPushButton("Experiment Default Setup")
        explayout.addWidget(dpbutton)
        dpbutton.clicked.connect(self.expDefault)

        self.expstopbutton = QPushButton("Stop Experiment")
        explayout.addWidget(self.expstopbutton)
        self.expstopbutton.clicked.connect(self.expstop)
        self.expstopbutton.setEnabled(False)

        camstream = QVBoxLayout()

        streambuttonlayout = QVBoxLayout()

        self.camerastream_button = QPushButton("Start Streaming",self)
        streambuttonlayout.addWidget(self.camerastream_button)
        self.camerastream_button.clicked.connect(self.CamStream)

        self.stopstream_button = QPushButton("Stop Streaming",self)
        streambuttonlayout.addWidget(self.stopstream_button)
        self.stopstream_button.clicked.connect(self.StopStream)
        self.stopstream_button.setEnabled(False)

        self.stream_label = QLabel('Camera Stream')
        self.stream_panel = QLabel(self)
        self.stream_panel.setPixmap(QPixmap(r"C:\Users\CaFMOT\Desktop\imgs\stream_background.tif"))
        camstream.addWidget(self.stream_label)
        camstream.addWidget(self.stream_panel)
        camstream.addLayout(streambuttonlayout)


        layout.addLayout(right_layout)


        generalUI.addLayout(layout)
        generalUI.addLayout(explayout)

        Applayout = QHBoxLayout()
        Applayout.addLayout(generalUI)
        Applayout.addLayout(camstream)


        self.setLayout(Applayout)


        self.worker_thread = None

    ## Set up default values for generating AWG frequencies
    def default_tweezer(self):
        self.central_freq_input.setText('170')
        self.freq_spacing_input.setText('0')
        self.freq_number_input.setText('1')
        self.freq_ramp_scope_input.setText('12')
        self.amp_ramp_scope_input.setText('0')
        self.ramp_time_input.setText('5')
        self.collective_amplitude_input.setText('0.13')
        

    ## Frequencies generation
    ## Contains everything necessary for the 'Generate Array' button
        
    def array(self):
        global freqs,central_freq,num_freq,freq_spacing,collective_amplitude,firstramp,\
               amp_list
        try:
            firstramp = True
            collective_amplitude = float(self.collective_amplitude_input.text())
            central_freq = int(self.central_freq_input.text())*(10**6)
            freq_spacing = int(self.freq_spacing_input.text())*(10**6)
            num_freq = int(self.freq_number_input.text())
            if num_freq % 2 == 1:
                half_num = (num_freq-1) / 2
                initial_freq = central_freq - freq_spacing * half_num
                last_freq = central_freq + freq_spacing * half_num
            elif num_freq % 2 == 0:
                half_num = (num_freq / 2) - 1
                initial_freq = central_freq - freq_spacing * half_num
                last_freq = central_freq + freq_spacing * (half_num + 2)
            freqs = np.linspace(initial_freq,last_freq,num_freq)
            amp_list = []
            eta = []
            for freq in freqs:
                freq = freq/(10**6)
                eta.append((collective_amplitude)/0.14\
                           *((116.9735*(1/(3.98544*math.sqrt(2*np.pi))*np.exp(-1/2*(((freq-181)/3.98544)**2)))+0.507)))
            s = (sum(eta))
            for i in eta:
                amp_list.append(s/i*0.045/7.294)
            print(amp_list)
            list_freqs = list(freqs)
            for freq in list_freqs:
                freq = freq/(10**6)
                if freq <= 169 and freq >= 160:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.18 #0.2
                elif (freq <= 179 and freq >= 170):
                    amp_list[list_freqs.index(freq*(10**6))] += 0.05 #0.045
                elif freq >= 180 and freq <= 185:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.042 #0.041
                elif freq <= 199 and freq >= 190:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.03 #0.036
                elif freq >= 200 and freq < 210:
                    amp_list[list_freqs.index(freq*(10**6))] -= 0.01 #-0.012
                elif freq <= 159 and freq >= 150:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.18 #0.2
                elif freq <= 149 and freq >= 140:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.03 #0.03
                elif freq >= 210:
                    amp_list[list_freqs.index(freq*(10**6))] += 0.1 #0.1
            amp_sum = sum(amp_list)
            for amp in amp_list:
                amp_updated = (collective_amplitude/amp_sum)*amp
                amp_list[amp_list.index(amp)] = amp_updated
            self.text_panel.append(f'Current amplitudes: {amp_list}')
            self.text_panel.append(f'Actual collective amplitude: {sum(amp_list)}')
            for i in freqs:
                self.select_chirp_input.addItem(str(i/(10**6))+' MHz')
            self.select_chirp_input.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.ramp_button.setEnabled(True)
            self.freq_ramp_scope_input.setEnabled(True)
            self.amp_ramp_scope_input.setEnabled(True)
            self.ramp_time_input.setEnabled(True)
            self.ontweezer_input.setEnabled(True)
            self.update_button.setEnabled(True)
            self.auto_button.setEnabled(True)
            self.array_button.setEnabled(False)
        except Exception as error:
            self.text_panel.append(f'Error 1: {error}')
            traceback.print_exc()
        try:
            self.arraythread = arraythread(freqs,num_freq,collective_amplitude,amp_list)
            self.arraythread.start()
            self.text_panel.append("Array generated.")
        except Exception as error:
            self.text_panel.append(f'Error 2: {error}')

    ## Linearly ramp the amplitude and/or frequency of the selected frequency
    def ramp(self):
        global freqs_list,firstramp,core_index
        try:
            freq_slope = float(self.freq_ramp_scope_input.text())*(10**6)
            amp_slope = float(self.amp_ramp_scope_input.text())
            ramp_time = float(self.ramp_time_input.text())
            s = self.select_chirp_input.currentText()
            freq_value_0 = float(re.findall(r"[-+]?\d*\.\d+|\d+",s)[0])
            if firstramp:
                freqs_list = list(freqs)
            print(freqs_list)
            freq_value = freq_value_0*(10**6)
            core_index = freqs_list.index(freq_value)
            self.text_panel.append('-------------------------------')
            self.text_panel.append(f'Frequency selected. Index: {core_index}')
            self.text_panel.append(f'Current frequency slope: {freq_slope/(10**6)} MHz/s')
            self.text_panel.append(f'Selected core\'s amplitude: {amp_list[core_index]}')
            self.rampthread = rampthread(core_index,freq_slope,amp_slope,\
                                         ramp_time,num_freq,freqs_list,\
                                         collective_amplitude,amp_list)
            self.rampthread.start()
            self.select_chirp_input.setItemText(freqs_list.index(freq_value),str((freqs_list[core_index]+\
                                                freq_slope*ramp_time)/(10**6))+' MHz')
            self.text_panel.append(f'Running...')
            amp_list[core_index]=amp_list[core_index]+amp_slope*ramp_time
            firstramp = False
            self.rampthread.rampthreadend.connect(self.rampfinished)
        except Exception as error:
            self.text_panel.append(f'Ramp error: {error}')

    def rampfinished(self,amp_list,core_index):
        try:
            self.text_panel.append('Ramp finished')
            self.text_panel.append(f'Current amplitude: {amp_list[core_index]}')
            self.text_panel.append('-------------------------------')
        except Exception as error:
            self.text_panel.append(f'Finished error: {error}')
            

    ## Turn off unused frequencies
    def update(self):
        try:
            freq_on = self.ontweezer_input.text()
            self.text_panel.append(f'{freq_on}')
            self.text_panel.append("Frequencies upadted. Unwanted ones have been turned off")
            for i in range(len(freq_on)):
                card.amp(int(freq_on[i]),0)
            card.exec_now()
            card.write_to_card()
        except Exception as error:
            self.text_panel.append(f'Update error: {error}')

        
    ## Stop frequency generation
    def stop(self):
        try:
            self.text_panel.append("Stop!")
            card.dds_reset()
            self.select_chirp_input.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.ramp_button.setEnabled(False)
            self.freq_ramp_scope_input.setEnabled(False)
            self.amp_ramp_scope_input.setEnabled(False)
            self.ramp_time_input.setEnabled(False)
            self.ontweezer_input.setEnabled(False)
            self.update_button.setEnabled(False)
            self.array_button.setEnabled(True)
            self.auto_button.setEnabled(False)
            self.select_chirp_input.clear()
            self.freq_ramp_scope_input.clear()
            self.amp_ramp_scope_input.clear()
            self.ramp_time_input.clear()
        except Exception as error:
            self.text_panel.append(f'Stop error: {error}')

    ## A simple setup: turn off the selected frequencies, and chirp
    ## the remaining ones closer to the lowest frequency 
    def auto(self):
        try:
            print('Auto starts')
            self.text_panel.append('////////////////////////')
            self.text_panel.append('Turning off unused frequencies...')
            ramp_time = float(self.ramp_time_input.text())
            freqs_list = list(freqs)
            nphotos = int(self.nphotos_input.text())
            freq_on = self.ontweezer_input.text()
            exptime = int(self.exptime_input.text())
            heading = self.heading_input.text()
            self.auto_thread = autothread(ramp_time,freqs_list,nphotos,num_freq,freq_on,freq_spacing,heading,amp_list)
            self.text_panel.append('Chirping remaining ones...')
            self.image_thread = imagethread(nphotos,heading,exptime)
            self.auto_thread.start()
            self.image_thread.start()
            self.auto_thread.autoend.connect(self.auto_finished)
        except Exception as error:
            self.text_panel.append(f'Auto error: {error}')
            traceback.print_exc()

    def auto_finished(self):
        self.text_panel.append('Auto rearrangement finished. Photos have been saved.')
        self.text_panel.append('////////////////////////')

    def expstop(self):
        global card_start
        if self.exp_thread and self.exp_thread.isRunning():
            self.exp_thread.terminate()
            self.text_panel.append("Experiment has been stopped")
            self.text_panel.append('======================')
            card_start = True
            self.expstopbutton.setEnabled(True)
            self.camerastart_button.setEnabled(True)


    def CamStream(self):
        try:
            exptime = float(self.exptime_input.text())
            borderline = self.borderline_input.isChecked()
            num_freq = int(self.freq_number_input.text())
            self.stream_thread = CamStreamThread(exptime,borderline,num_freq)
            self.stream_thread.stream_frame.connect(self.update_frame)
            self.stream_thread.start()
            self.stopstream_button.setEnabled(True)
            self.camerastream_button.setEnabled(False)
            self.camerastart_button.setEnabled(False)
        except Exception as error:
            print(f'Cam Stream error: {error}')

    def update_frame(self,pixmap):
        self.stream_panel.setPixmap(pixmap)
        

    def StopStream(self):
        try:
            self.nphotos = 0
            self.exptime = 0
            command = str([self.nphotos,self.exptime,2])
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.connect((server_ip,12345))
                s.sendall(command.encode())
                print('Command has been sent')
##                while stop_sign != '1':
##                stop_sign = s.recv(3)
##            stop_sign = str(stop_sign)
##            signal = stop_sign[2]
##            print(stop_sign[2])
##            print(type(signal))
##            if self.stream_thread and self.stream_thread.isRunning() and stop_sign=='1':
##                self.stream_thread.terminate()
##                print('Stream thread terminated')
            self.stopstream_button.setEnabled(False)
            self.camerastream_button.setEnabled(True)
            self.camerastart_button.setEnabled(True)
            
        except Exception as error:
            self.text_panel.append('Streaming end error: {error}')
            traceback.print_exc()

    def CamStart(self):
        global freqs
        try:
            plot_freq_list = []
            self.text_panel.append("Aquiring parameters...") 
            nphotos = int(self.nphotos_input.text())
            exptime = float(self.exptime_input.text())
            gain = float(self.gain_input.text())
            heading = self.heading_input.text()
            imganalysis = self.imganalysis_input.isChecked()
            intensityanalysis = self.analysis_input.isChecked()
            borderline = self.borderline_input.isChecked()
            crop = self.crop_input.isChecked()
            self.text_panel.append("Camera settings updated")
            freqs = list(freqs)
            for freq in freqs:
                freq_MHz = freq/(10**6)
                plot_freq_list.append(freq_MHz)
            print(f'Current on frequencies: {plot_freq_list}')
            self.camera_thread = CameraThread(nphotos,exptime,\
                                              heading,gain,imganalysis,num_freq,borderline,\
                                              intensityanalysis,plot_freq_list,crop)
            self.camera_thread.cameraend.connect(self.camera_finished)
            self.camera_thread.start()
            print('Thread started')
        except Exception as error:
            self.text_panel.append(f'Camera error 2: {error}')
            traceback.print_exc()
            
    def camera_finished(self,imganalysis,heading,nphotos,on_list,num_on,count_list,MaxIntensity,threshold,\
                        intensityanalysis,crop):

        try:
            if imganalysis == True:
                self.text_panel.append(f'Photo analysed. Number of occupied tweezers: {num_on}')
                self.text_panel.append(f'List of occupied tweezers: {on_list}')
                self.text_panel.append(f'Current pixel count threshold; {threshold}')
                self.text_panel.append(f'Count of bright pixels in each subregion: {count_list}')
                self.text_panel.append(f'Maximum Intensity of the last photo taken: {MaxIntensity}')
            elif imganalysis == False:
                pass

            if intensityanalysis == True:
                popup = ImagePopup(rf"C:\Users\CaFMOT\Desktop\MOTImages\analysis.png")
                popup.exec_()
            else:
                pass

            self.text_panel.append('Photos have been taken')
            if crop == True:
                self.photopanel.setPixmap(QPixmap(rf"C:\Users\CaFMOT\Desktop\MOTImages\{heading}_{nphotos}.tif"))
                self.location.setText(f"{heading}{nphotos}.tif")
        except Exception as error:
            self.text_panel.append(f'Cam finished error: {error}')
            traceback.print_exc()

    def Default(self):
        self.nphotos_input.setText('1')
        self.exptime_input.setText('65')
        self.gain_input.setText('10.6')
        self.heading_input.setText('Default')

    def expDefault(self):
        self.exptime_input.setText('120')
        self.heading_input.setText('Exp')
        self.central_freq_input.setText('180')
        self.freq_number_input.setText('5')
        self.ramp_time_input.setText('3')
        self.freq_spacing_input.setText('10')
        self.collective_amplitude_input.setText('0.18')
        self.nphotos_input.setText('5')

    def expStart(self):
        global card_start
        try:
            exptime = int(self.exptime_input.text())
            heading = self.heading_input.text()
            central_freq = int(self.central_freq_input.text())
            num_freq = int(self.freq_number_input.text())
            ramp_time = float(self.ramp_time_input.text())
            freq_spacing = int(self.freq_spacing_input.text())
            iteration = int(self.nphotos_input.text())
            collective_amplitude = float(self.collective_amplitude_input.text())
            self.text_panel.append('======================')
            self.text_panel.append("Mock Exp start")
            self.expstopbutton.setEnabled(True)
            self.camerastart_button.setEnabled(False)
        except Exception as error:
             self.text_panel.append(f'Exp start init error: {error}')
             traceback.print_exc() 
        try:
            self.exp_thread = ExpThread(exptime,heading,central_freq,collective_amplitude,\
                                        num_freq,ramp_time,freq_spacing,iteration,card_start)
            self.exp_thread.iterationend.connect(self.iteration_finished)
            self.exp_thread.start()
            self.exp_thread.expend.connect(self.exp_finished)
        except Exception as error:
            self.text_panel.append(f'Exp start error: {error}')
            traceback.print_exc()

    def Clear(self):
        self.text_panel.clear()
        self.photopanel.setPixmap(QPixmap(r"C:\Users\CaFMOT\Desktop\imgs\background.tif"))

    def exp_finished(self):
        global card_start
        self.text_panel.append('Mock Exp finished')
        self.text_panel.append('======================')
        card_start = True
        self.camerastart_button.setEnabled(True)

    def iteration_finished(self,itr,off_freqs,list_freqs):
        self.text_panel.append(f'Iteration {itr+1} has been completed')
        self.text_panel.append(f'The unoccupied frequencies are {off_freqs}')
        self.text_panel.append(f'Currently turned on frequencies: {list_freqs}')

class ImagePopup(QDialog):
    def __init__(self,image_path):
        super().__init__()
        self.setWindowTitle("Intensity Result")
        layout = QVBoxLayout()
        self.setLayout(layout)
        image_label = QLabel(self)
        image_label.setPixmap(QPixmap(image_path))

        layout.addWidget(image_label)
 
class arraythread(QThread):
    global card_start
    arraythreadend = pyqtSignal()
    global amp_list

    def __init__(self,freqs,num_freq,collective_amplitude,amp_list):
        super().__init__()
        self.freqs = freqs
        self.num_freq = num_freq
        self.collective_amplitude = collective_amplitude
        self.amp_list = amp_list
        
    def run(self):
        try:
            card.dds_reset()
            for i,freq in enumerate(self.freqs):
##                card.amp(i,amp_list[i])
                card.amp(i,float(self.collective_amplitude/self.num_freq))
                card.freq(i,freq)
            card.exec_at_trg()
            
            card.write_to_card()
            if not card_start:
                card.start(spcm.M2CMD_CARD_WAITREADY, spcm.M2CMD_CARD_ENABLETRIGGER)
                card.start = True
            self.text_panel.append("Array generated")
        except Exception as error:
            print(f'Warning: {error}. Operations normal')

# Note that this thread still uses the amp_list to determine the amplitude of each tone, which is
# now currently NOT used for the generation of array. Advice: do not do amplitude ramp at the
# moment.

class rampthread(QThread):
    rampthreadend = pyqtSignal(list,int)

    def __init__(self,core_index,freq_slope,amp_slope,ramp_time,num_freq,\
                 freqs_list,collective_amplitude,amp_list):
        try:
            super().__init__()
            self.core_index = core_index
            self.freq_slope = freq_slope
            self.amp_slope = amp_slope
            self.ramp_time = ramp_time
            self.num_freq = num_freq
            self.freqs_list = freqs_list
            self.collective_amplitude = collective_amplitude
            self.amp_list = amp_list
        except Exception as error:
            print(f'Ramp thread initialization error: {error}')

    def run(self):
        global freqs_list
        try:
            print(self.amp_list)
            card.frequency_slope(self.core_index,self.freq_slope)
            try:
                card.amp_ramp_stepsize(1000)
                card.amplitude_slope(self.core_index,self.amp_slope)
            except Exception as error:
                print(f'Ramp thread error 1: {error}')
            card.exec_now()
            card.write_to_card()
            time.sleep(self.ramp_time)

            card.amplitude_slope(self.core_index,0)
            card.frequency_slope(self.core_index,0)
            card.amp(self.core_index,self.amp_list[self.core_index]+self.amp_slope*self.ramp_time)
            card.frequency(self.core_index,float(self.freqs_list[self.core_index])+\
                           self.freq_slope*self.ramp_time)
            card.exec_now()
            card.write_to_card()
            self.freqs_list[self.core_index] = float(self.freqs_list[self.core_index]+\
                           self.freq_slope*self.ramp_time)
            self.amp_list[self.core_index] = float(self.amp_list[self.core_index]+\
                                                   self.amp_slope*self.ramp_time)
            freqs_list = self.freqs_list
            print(self.amp_list)
            amp_list = self.amp_list
            core_index = self.core_index
            self.rampthreadend.emit(amp_list,core_index)
        except Exception as error:
            print(f'Ramp thread error: {error}')

class CameraThread(QThread):
    cameraend = pyqtSignal(bool,str,int,list,int,list,int,int,bool,bool)

    def __init__(self,nphotos,exptime,heading,gain,imganalysis,num_freq,borderline,intensityanalysis,plot_freq_list,crop):
        super().__init__()
        self.nphotos = nphotos
        self.exptime = exptime
        self.heading = heading
        self.gain = gain
        self.imganalysis = imganalysis
        self.num_freq = num_freq
        self.borderline = borderline
        self.intensityanalysis = intensityanalysis
        self.plot_freq_list = plot_freq_list
        self.crop = crop
        print('Initialized')

    def run(self):
        try:
            images = send_command(server_ip,str([self.nphotos,self.exptime,0]),self.nphotos)
            print('Images received')
            outputpath = r"C:\Users\CaFMOT\Desktop\MOTImages"
            os.makedirs(outputpath,exist_ok=True)
            for i, image_array in enumerate(images):
                if self.num_freq <=5:
                    strip = image_array[210:280, 80:300]
                    if self.borderline:
                        strip[:,56:58]=255
                        strip[:,88:90]=255
                        strip[:,116:118]=255
                        strip[:,142:144]=255
                elif self.num_freq <= 7:
                    strip = image_array[210:280, 20:360]
                    if self.borderline:
                        strip[:,87:89]=255
                        strip[:,116:118]=255
                        strip[:,145:147]=255
                        strip[:,172:174]=255
                        strip[:,206:208]=255
                        strip[:,239:241]=255
                else:
                    strip = image_array[200:280, 0:480]
                filename = f"{self.heading}_{i+1}.tif"
                filepath = os.path.join(outputpath,filename)
                if self.crop:
                    tiff.imsave(filepath, strip)
                else:
                    tiff.imsave(filepath,image_array)
            heading = self.heading
            nphotos = self.nphotos
            imganalysis = self.imganalysis
            
            if imganalysis == True:
                on_list = []
                num_on = 0
                count_list = []
                if self.num_freq <= 5:
                    threshold = 550*self.exptime/120 # 200*exptime/200
                    region_0 = strip[:,0:56]
                    count1 = np.count_nonzero(region_0>=50)
                    if count1 >= threshold:
                        on_list.append('0')
                        num_on+=1
                    count_list.append(count1)
                    region_1 = strip[:,57:87]
                    count2 = np.count_nonzero(region_1>=50)
                    if count2 >= threshold:
                        on_list.append('1')
                        num_on+=1
                    count_list.append(count2)
                    region_2 = strip[:,88:116]
                    count3 = np.count_nonzero(region_2>=50)
                    if count3 >= threshold:
                        on_list.append('2')
                        num_on+=1
                    count_list.append(count3)
                    region_3 = strip[:,117:143]
                    count_4 = np.count_nonzero(region_3>=50)
                    if count_4 >= threshold:
                        on_list.append('3')
                        num_on+=1
                    count_list.append(count_4)
                    region_4 = strip[:,144:220]
                    count_5 = np.count_nonzero(region_4>=50)
                    if count_5 >= threshold:
                        on_list.append('4')
                        num_on+=1
                    count_list.append(count_5)

                    MaxIntensity = 'Nil'

                elif self.num_freq <= 7:
                    threshold = 0
                    region_0 = strip[:,0:87]
                    count1 = np.count_nonzero(region_0>=50)
                    if count1 >= 700*self.exptime/500:
                        on_list.append('0')
                        num_on+=1
                    count_list.append(count1)
                    
                    region_1 = strip[:,88:116]
                    count2 = np.count_nonzero(region_1>=50)
                    if count2 >= 300*self.exptime/500:
                        on_list.append('1')
                        num_on+=1
                    count_list.append(count2)
                    
                    region_2 = strip[:,117:145]
                    count3 = np.count_nonzero(region_2>=50)
                    if count3 >= 300*self.exptime/500:
                        on_list.append('2')
                        num_on+=1
                    count_list.append(count3)

                    region_3 = strip[:,146:171]
                    count4 = np.count_nonzero(region_3>=50)
                    if count4 >= 300*self.exptime/600:
                        on_list.append('3')
                        num_on+=1
                    count_list.append(count4)

                    region_4 = strip[:,172:206]
                    count5 = np.count_nonzero(region_4>=50)
                    if count5 >= 200:
                        on_list.append('4')
                        num_on+=1
                    count_list.append(count5)

                    region_5 = strip[:,207:238]
                    count6 = np.count_nonzero(region_5>=50)
                    if count6 >= 200:
                        on_list.append('5')
                        num_on+=1
                    count_list.append(count6)

                    region_6 = strip[:,239:340]
                    count7 = np.count_nonzero(region_6>=50)
                    if count7 >= 200:
                        on_list.append('6')
                        num_on+=1
                    count_list.append(count7)

                    MaxIntensity = 'Not analysed'
##                result = greyintensity(rf"C:\Users\CaFMOT\Desktop\MOTImages\{self.heading}_{i+1}.tif")
##                pixeldata = result[1]
##                MaxIntensity = max(pixeldata)
                
                                       
            else:
                on_list = []
                num_on = 0
                count_list = []
                MaxIntensity = 0
                threshold = 0
                crop = self.crop

            print('Proceed!')

            if self.intensityanalysis == True:
                if num_freq==5:
                    region_0 = strip[:,0:56]
                    region_1 = strip[:,57:87]
                    region_2 = strip[:,88:116]
                    region_3 = strip[:,117:143]
                    region_4 = strip[:,144:220]
                    max_0 = np.max(region_0)
                    max_1 = np.max(region_1)
                    max_2 = np.max(region_2)
                    max_3 = np.max(region_3)
                    max_4 = np.max(region_4)
                    intensitymax = [max_0,max_1,max_2,max_3,max_4]
                    gauss = []
                    extended_freq_list = list(np.linspace(self.plot_freq_list[0],self.plot_freq_list[4],21))
                    print(freqs)
                    for i in range(21):
                        gauss.append(Gaussian(extended_freq_list[i],self.plot_freq_list[0],0.6,intensitymax[0]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[1],0.6,intensitymax[1]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[2],0.6,intensitymax[2]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[3],0.6,intensitymax[3]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[4],0.6,intensitymax[4]*math.sqrt(2*math.pi)*0.6))
                    plt.plot(extended_freq_list,gauss,linestyle='-',color='r')
                    plt.xlabel('Frequencies / MHz')
                    plt.ylabel('Maximum Intensity')
                    plt.savefig(rf"C:\Users\CaFMOT\Desktop\MOTImages\analysis.png",dpi=100)
                    plt.clf()
                elif num_freq==7:
                    region_0 = strip[:,0:87]
                    region_1 = strip[:,88:116]
                    region_2 = strip[:,117:145]
                    region_3 = strip[:,146:171]
                    region_4 = strip[:,172:206]
                    region_5 = strip[:,207:238]
                    region_6 = strip[:,239:340]
                    max_0 = np.max(region_0)
                    max_1 = np.max(region_1)
                    max_2 = np.max(region_2)
                    max_3 = np.max(region_3)
                    max_4 = np.max(region_4)
                    max_5 = np.max(region_5)
                    max_6 = np.max(region_6)
                    intensitymax = [max_0,max_1,max_2,max_3,max_4,max_5,max_6]
                    gauss = []
                    extended_freq_list = list(np.linspace(self.plot_freq_list[0],self.plot_freq_list[6],25))
                    print(extended_freq_list)
                    print(freqs)
                    for i in range(25):
                        gauss.append(Gaussian(extended_freq_list[i],self.plot_freq_list[0],0.6,intensitymax[0]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[1],0.6,intensitymax[1]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[2],0.6,intensitymax[2]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[3],0.6,intensitymax[3]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[4],0.6,intensitymax[4]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[5],0.6,intensitymax[5]*math.sqrt(2*math.pi)*0.6)+\
                                     Gaussian(extended_freq_list[i],self.plot_freq_list[6],0.6,intensitymax[6]*math.sqrt(2*math.pi)*0.6))
                    plt.plot(extended_freq_list,gauss,linestyle='-',color='r')
                    plt.xlabel('Frequencies / MHz')
                    plt.ylabel('Maximum Intensity')
                    plt.savefig(rf"C:\Users\CaFMOT\Desktop\MOTImages\analysis.png",dpi=100)
                    plt.clf()
                else:
                    pass
            print('Proceed!')
            print('Before signal')
            crop = self.crop
            print('Ready to send the signal..')
            self.cameraend.emit(imganalysis,heading,nphotos,on_list,num_on,count_list,MaxIntensity,threshold,\
                                self.intensityanalysis,crop)
            print('Signal sent!')
        except Exception as err:
            print(f"Camera end signal error: {err}")
            traceback.print_exc()

class CamStreamThread(QThread):
    stream_frame = pyqtSignal(QPixmap)
    
    def __init__(self,exptime,borderline,num_freq):
        super().__init__()
        self.exptime = exptime
        self.borderline = borderline
        self.num_freq = num_freq

    def run(self):
        try:
            self.nphotos = 0
            command = str([self.nphotos,self.exptime,1])
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.connect(('155.198.206.58',12345))
                s.sendall(command.encode())
                while True:
                    received_data = s.recv(307360)
                    if len(received_data) == 307360:
                        try:
                            image_frame = pickle.loads(received_data)
                            if self.borderline == True:
                                if self.num_freq == 5:
                                    image_frame[:,136:138]=255
                                    image_frame[:,168:170]=255
                                    image_frame[:,196:198]=255
                                    image_frame[:,222:224]=255
                                elif self.num_freq == 7:
                                    image_frame[:,167:169]=255
                                    image_frame[:,196:198]=255
                                    image_frame[:,225:227]=255
                                    image_frame[:,252:254]=255
                                    image_frame[:,286:288]=255
                                    image_frame[:,319:321]=255
                                elif self.num_freq == 999:
                                    for i in range(0,640,20):
                                        image_frame[:,i]=255
                                else:
                                    pass
                            else:
                                pass
                            height,width = image_frame.shape
                            acquired_frame = QImage(image_frame.data,width,height,width,QImage.Format_Grayscale8)
                            pixmap = QPixmap.fromImage(acquired_frame)
                            self.stream_frame.emit(pixmap)
                        except Exception:
                            pass
                    else:
                        pass
        except Exception as err:
            print(f"Camera streaming error: {err}")
            traceback.print_exc()


class imagethread(QThread):
    def __init__(self,nphotos,heading,exptime):
        super().__init__()
        self.nphotos = nphotos
        self.heading = heading
        self.exptime = exptime
        print('OK_image')
        
    def run(self):
        try:
            images = send_command(server_ip,str([self.nphotos,self.exptime,0]),self.nphotos)
            outputpath = r"C:\Users\CaFMOT\Desktop\MOTImages"
            os.makedirs(outputpath,exist_ok=True)
            for i, image_array in enumerate(images):
                filename = f"{self.heading}_{i+1}.tif"
                filepath = os.path.join(outputpath,filename)
                tiff.imsave(filepath, image_array)
            print('Image thread: images saved!')
        except Exception as error:
            print('Image thread error: {error}')
            traceback.print_exc()

class autothread(QThread):
    autoend = pyqtSignal()

    def __init__(self,ramp_time,freqs_list,nphotos,num_freq,freq_on,freq_spacing,heading,amp_list):
        super().__init__()
        self.nphotos = nphotos
        self.ramp_time = ramp_time
        self.freqs_list = freqs_list
        self.num_freq = num_freq
        self.freq_on = freq_on
        self.freq_spacing = freq_spacing
        self.heading = heading
        self.amp_list = amp_list
        print('OK')

    def run(self):
        try:
            print('OK')
            activate_core_list = []
            for i in range(self.num_freq):
                activate_core_list.append(i)
            for i in range(len(self.freq_on)):
                card.amp(int(self.freq_on[i]),0)
                activate_core_list.remove(int(self.freq_on[i]))
                self.freqs_list[int(self.freq_on[i])]= i
                self.amp_list[int(self.freq_on[i])]= i
                
            card.exec_now()
            card.write_to_card()

            for i in range(len(self.freq_on)):
                self.freqs_list.remove(i)
                
            ramped_freq_list = []
            ramped_freq_list.append(self.freqs_list[0])
            for i in range(len(activate_core_list)-1):
                ramped_freq_list.append(self.freqs_list[0]+self.freq_spacing*(i+1))
            delta_freq = np.subtract(np.array(ramped_freq_list),np.array(self.freqs_list))
            delta_freq = list(delta_freq)
            for i,j in enumerate(activate_core_list):
                card.frequency_slope(j,delta_freq[i]/self.ramp_time)
            card.exec_now()
            card.write_to_card()
            time.sleep(self.ramp_time)
            for i,j in enumerate(activate_core_list):
                card.frequency(j, ramped_freq_list[i])
                card.frequency_slope(j,0)
            card.exec_now()
            card.write_to_card()
            print('Auto thread completed')
            self.autoend.emit()
            
        except Exception as err:
            print(f"Auto thread error: {err}")
            traceback.print_exc()

class ExpThread(QThread):
    expend = pyqtSignal(bool)
    iterationend = pyqtSignal(int,list,list)

    
    def __init__(self,exptime,heading,central_freq,collective_amplitude,\
                 num_freq,ramp_time,freq_spacing,iteration,card_start):
        super().__init__()
        self.iteration = iteration
        self.exptime = exptime
        self.heading = heading
        self.central_freq = central_freq
        self.num_freq = num_freq
        self.ramp_time = ramp_time
        self.freq_spacing = freq_spacing
        self.collective_amplitude = collective_amplitude
        self.card_start = card_start

    def run(self):
        try:
            exptime = self.exptime
            heading = self.heading
            iteration = self.iteration
            central_freq = self.central_freq
            freq_spacing = self.freq_spacing
            collective_amplitude = self.collective_amplitude
            num_freq = self.num_freq
            ramp_time = self.ramp_time
            
            ## Generate Frequencies
            for itr in range(iteration):
                if num_freq % 2 == 1:
                    half_num = (num_freq-1) / 2
                    initial_freq = central_freq - freq_spacing * half_num
                    last_freq = central_freq + freq_spacing * half_num
                elif num_freq % 2 == 0:
                    half_num = (num_freq / 2) - 1
                    initial_freq = central_freq - freq_spacing * half_num
                    last_freq = central_freq + freq_spacing * (half_num + 2)
                freqs = np.linspace(initial_freq,last_freq,num_freq)
                exp_amp_list = []
                eta = []
                for freq in freqs:
                    eta.append((collective_amplitude)/0.14\
                               *((116.9735*(1/(3.98544*math.sqrt(2*np.pi))*np.exp(-1/2*(((freq-181)/3.98544)**2)))+0.507)))
                s = (sum(eta))
                for i in eta:
                    exp_amp_list.append(s/i*0.045/7.294)
                list_freqs = list(freqs)
                for freq in list_freqs:
                    if freq <= 169 and freq >= 160:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.22 #0.2
                    elif (freq <= 179 and freq >= 170):
                        exp_amp_list[list_freqs.index(freq*1)] += 0.055 #0.045
                    elif freq >= 180 and freq <= 185:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.042 #0.041
                    elif freq <= 199 and freq >= 190:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.041 #0.036
                    elif freq >= 200 and freq < 210:
                        exp_amp_list[list_freqs.index(freq*1)] -= 0.018 #-0.012
                    elif freq <= 159 and freq >= 150:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.18 #0.2
                    elif freq <= 149 and freq >= 140:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.03 #0.03
                    elif freq >= 210:
                        exp_amp_list[list_freqs.index(freq*1)] += 0.2 #0.1
                amp_sum = sum(exp_amp_list)
                for amp in exp_amp_list:
                    amp_updated = (collective_amplitude/amp_sum)*amp
                    exp_amp_list[exp_amp_list.index(amp)] = amp_updated
                print(f'Current amplitudes: {exp_amp_list}')
                print(f'Actual collective amplitude: {sum(exp_amp_list)}')
                print(f'Current frequencies: {freqs}')

                ## Write to card and execute
                card.dds_reset()
                for i,freq in enumerate(freqs):
                    card.amp(i,self.collective_amplitude/self.num_freq)
                    card.freq(i,freq*(10**6))
                card.exec_now()
                
                card.write_to_card()
                print('Data has been written to card')
                print(self.card_start)
                if not self.card_start:
                    card.start(spcm.M2CMD_CARD_START, spcm.M2CMD_CARD_ENABLETRIGGER)
                    self.card_start = True
                    print('Card has been started')

                ## Take a photo
                image_all_freqs = send_command(server_ip,str([1,exptime,0]),1)
                outputpath = r"C:\Users\CaFMOT\Desktop\MOTImages\MockExps"
                os.makedirs(outputpath,exist_ok=True)
                filename = f"{heading}_all_freqs_iteration{itr+1}.tif"
                filepath = os.path.join(outputpath,filename)
                tiff.imsave(filepath, image_all_freqs)

                ## Generate random numbers to represent 'off' frequencies
                rand_count = random.randint(0,num_freq)
                off_freqs = []
                if rand_count == 0:
                    pass
                elif rand_count == num_freq:
                    for i in range(num_freq):
                        off_freqs.append(i)
                else:
                    for i in range(rand_count):
                        new_entry = random.randint(0,4)
                        while new_entry in off_freqs:
                            new_entry = random.randint(0,4)
                        off_freqs.append(new_entry)
                off_freqs = sorted(off_freqs)
                print(off_freqs)
                for item in off_freqs:
                    list_freqs[int(item)] = item
                for item in off_freqs:
                    list_freqs.remove(item)
                print(f'Offed frequencies are: {off_freqs}')
                print(f'Current on frequencies: {list_freqs}')

                ## Turn off these frequecies
                if not (len(off_freqs)==0):
                    for i in range(len(off_freqs)):
                        card.amp(int(off_freqs[i]),0)
                        card.exec_now()
                        card.write_to_card()

                ## Take another picture to verify the unoccupied ones are turned off
                image_off_freqs_raw = send_command(server_ip,str([1,exptime,0]),1)
                if num_freq <=5:
                    image_off_freqs = image_off_freqs_raw[0][210:280, 80:300]
                elif num_freq <=7:
                    image_off_freqs = image_off_freqs_raw[0][210:280, 20:360]
                outputpath = r"C:\Users\CaFMOT\Desktop\MOTImages\MockExps"
                os.makedirs(outputpath,exist_ok=True)
                filename = f"{heading}_offed_freqs_iteration{itr+1}.tif"
                filepath = os.path.join(outputpath,filename)
                tiff.imsave(filepath, image_off_freqs)

                ## Analyse the photo, return the number of 'on' frequencies and their exact position
                on_list = []
                num_on = 0
                count_list = []
                if num_freq <= 5:
                    threshold = 550*exptime/120 # 200*exptime/200
                    region_0 = image_off_freqs[:,0:56]
                    count1 = np.count_nonzero(region_0>=50)
                    if count1 >= threshold:
                        on_list.append('0')
                        num_on+=1
                    count_list.append(count1)
                    region_1 = image_off_freqs[:,57:87]
                    count2 = np.count_nonzero(region_1>=50)
                    if count2 >= threshold:
                        on_list.append('1')
                        num_on+=1
                    count_list.append(count2)
                    region_2 = image_off_freqs[:,88:116]
                    count3 = np.count_nonzero(region_2>=50)
                    if count3 >= threshold:
                        on_list.append('2')
                        num_on+=1
                    count_list.append(count3)
                    region_3 = image_off_freqs[:,117:143]
                    count_4 = np.count_nonzero(region_3>=50)
                    if count_4 >= threshold:
                        on_list.append('3')
                        num_on+=1
                    count_list.append(count_4)
                    region_4 = image_off_freqs[:,144:220]
                    count_5 = np.count_nonzero(region_4>=50)
                    if count_5 >= threshold:
                        on_list.append('4')
                        num_on+=1
                    count_list.append(count_5)

                elif num_freq <= 7:
                    region_0 = image_off_freqs[:,0:86]
                    count1 = np.count_nonzero(region_0>=50)
                    if count1 >= 700*self.exptime/500:
                        on_list.append('0')
                        num_on+=1
                    count_list.append(count1)
                    
                    region_1 = image_off_freqs[:,87:119]
                    count2 = np.count_nonzero(region_1>=50)
                    if count2 >= 300*self.exptime/500:
                        on_list.append('1')
                        num_on+=1
                    count_list.append(count2)
                    
                    region_2 = image_off_freqs[:,120:154]
                    count3 = np.count_nonzero(region_2>=50)
                    if count3 >= 300*self.exptime/500:
                        on_list.append('2')
                        num_on+=1
                    count_list.append(count3)

                    region_3 = image_off_freqs[:,155:184]
                    count4 = np.count_nonzero(region_3>=50)
                    if count4 >= 300*self.exptime/600:
                        on_list.append('3')
                        num_on+=1
                    count_list.append(count4)

                    region_4 = image_off_freqs[:,185:219]
                    count5 = np.count_nonzero(region_4>=50)
                    if count5 >= 200:
                        on_list.append('4')
                        num_on+=1
                    count_list.append(count5)

                    region_5 = image_off_freqs[:,220:254]
                    count6 = np.count_nonzero(region_5>=50)
                    if count6 >= 200:
                        on_list.append('5')
                        num_on+=1
                    count_list.append(count6)

                    region_6 = image_off_freqs[:,255:340]
                    count7 = np.count_nonzero(region_6>=50)
                    if count7 >= 200:
                        on_list.append('6')
                        num_on+=1
                    count_list.append(count7)

                print(on_list)
                print(count_list)
                ## Chirp remaining ones together
                activate_core_list = []
                for i in on_list:
                    activate_core_list.append(int(i))
                    
                ramped_freq_list = []
                if rand_count == num_freq:
                    print('All tweezers are unoccupied...')
                else:
                    print(f'Activated cores: {activate_core_list}')
                    for i in range(len(activate_core_list)):
                        ramped_freq_list.append(list_freqs[0]+freq_spacing*(i))
                    delta_freq = np.subtract(np.array(ramped_freq_list),np.array(list_freqs))
                    delta_freq = list(delta_freq)
                    print(delta_freq)
                    print(ramped_freq_list)
                    for i,j in enumerate(activate_core_list):
                        card.frequency_slope(j,delta_freq[i]*(10**6)/ramp_time)
                    card.exec_now()
                    card.write_to_card()
                    time.sleep(self.ramp_time)
                    for i,j in enumerate(activate_core_list):
                        card.frequency(j, ramped_freq_list[i]*(10**6))
                        card.frequency_slope(j,0)
                    card.exec_now()
                    card.write_to_card()


                ## Take one last photo
                image_end_chirp = send_command(server_ip,str([1,exptime,0]),1)
                outputpath = r"C:\Users\CaFMOT\Desktop\MOTImages\MockExps"
                os.makedirs(outputpath,exist_ok=True)
                filename = f"{heading}_end_chirp_iteration{itr+1}.tif"
                filepath = os.path.join(outputpath,filename)
                tiff.imsave(filepath, image_end_chirp)

                ## Signal the end of one iteration
                self.iterationend.emit(itr,off_freqs,list_freqs)
            print('iterations finished!')
            self.expend.emit(self.card_start)
            
        except Exception as error:
            print(f"ExpThread error: {error}")
            traceback.print_exc()

def main():
    global card,cam
    print("Generating UI...")
    app = QApplication(sys.argv)
    dialog = UIDialog()
    dialog.show()
    sys.exit(app.exec_())
##    with spcm.DDS('/dev/spcm0') as card:
##        if card:
##            print('Card has been found')
##            num_channels = 1
##            card.set(spcm.SPC_CHENABLE, (0x1 << num_channels) - 1)
##            for channel_index in range(num_channels):
##                card.out_enable(channel_index, True)
##                card.out_amp(channel_index, 1000)
##            card.write_to_card()
##            card.dds_reset()
##            print("Card has been setup")
##            app = QApplication(sys.argv)
##            dialog = UIDialog()
##            dialog.show()
##            sys.exit(app.exec_())
##        else:
##            print('No card found')
if __name__ == "__main__":
    main()

            
