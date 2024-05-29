import numpy as np
import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTextEdit,QApplication,QComboBox,QMainWindow,QLabel,QVBoxLayout,QWidget,QDialog,QLineEdit,QPushButton,QHBoxLayout,QCheckBox,QFileDialog
from PyQt5.QtGui import QPixmap,QImage,QPainter,QFont
from PyQt5.QtCore import Qt,QPoint,QThread,pyqtSignal,pyqtSlot
import matplotlib.pyplot
matplotlib.use('Qt5Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import imageio
import time
from diffractio import mm,um
from diffractio.scalar_masks_XY import Scalar_mask_XY
from PIL import Image
import cv2
import socket
import pickle
import os
import statistics
import tifffile as tiff
import traceback
import cupy as cp
import csv


server_ip = '155.198.206.58'

def send_phase_mask(target_ip,mask_path):
    
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.connect((target_ip,12345))
        phase_mask = cv2.imread(mask_path,cv2.IMREAD_GRAYSCALE).flatten()
        command = [phase_mask,4]
        command = pickle.dumps(command)
        s.sendall(command)

        received_data = b''
        while True:
            packet = s.recv(100)
            if not packet:
                break
            received_data += packet
            break
        feedback = pickle.loads(received_data)

        return feedback
    
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

def image_intensity(image_path,start_row,start_col,num_regions):
    # For 8 by 8, spacing = 20, FInt = 20,FStd = 0 array
    
    path = r'D:\Academic Files\Project 23-24\Slices'
    os.makedirs(path,exist_ok = True)
    image = cv2.imread(image_path,cv2.IMREAD_GRAYSCALE)
##    start_row = 291
##    start_col = 100 # 214
    spacing = 4
##    num_regions = 4 # 8

    regions = {}

    for i in range(1,num_regions+1):

        for j in range(1,num_regions +1):

            row_start = start_row + (i-1)*spacing
            row_end = start_row+3+(i-1)*spacing
            col_start = start_col + (j-1)*spacing
            col_end = start_col+3+(j-1)*spacing

            regionname = f'region{i}{j}'
            regions[regionname] = image[row_start:row_end,col_start:col_end]
            region = image[row_start:row_end,col_start:col_end]
            tiff.imwrite(os.path.join(path,f'region_{i}{j}.tiff'),region)

    intensity_list = []

    # ------------- Average the intensities along two directions, then pick the mean value -----------#
##    for region_name,region_array in regions.items():
##        average_x_int = []
##        average_y_int = []
##        for i in range(3):
##            sum_col = 0
##            for j in range(3):
##                sum_col += region_array[i,j]
##            mean_int_row = sum_col / 3
##            average_y_int.append(mean_int_row)
##        int_value_y = max(average_y_int)
##
##        for j in range(3):
##            sum_row = 0
##            for i in range(3):
##                sum_row += region_array[i,j]
##            mean_int_col = sum_row / 3
##            average_x_int.append(mean_int_col)
##        int_value_x = max(average_x_int)
##
##        intensity = (int_value_x+int_value_y)/2
##        intensity_list.append(intensity)
    # -------------------------------------------------------------------------------------------------#



    # ------------------------ Sum up all the intensities within region of interest --------------------------#
    for region_name,region_array in regions.items():
        intensity_sum = 0
        for i in range(3):
            for j in range(3):
                intensity_sum += region_array[i,j]
        intensity_list.append(intensity_sum)
    # --------------------------------------------------------------------------------------------------------#
        
    intensity_array = np.array(intensity_list)
    intensity_array_2D = intensity_array.reshape((num_regions,num_regions))
    mean_intensity = sum(intensity_array)/len(intensity_array)
    std_intensity = statistics.stdev(intensity_array)

    return intensity_array_2D,mean_intensity,std_intensity
    
# Disclaimer #
# This GS algorithm is based on the work done by previous UROP student #
# Almost no changes to the original work #
# Well, seems that this is provided by Meadowlarks Optics #

##def GS_algo(beam,pattern,pm_s,h,w,iterations):

##    # beam: incident beam. Ideally should be a 2D Gaussian
##    # pattern: Desired output pattern at the Fourier Plane. Superposition of
##    # multiple 2D Gaussian Beams
##
##    pm_f = np.random.rand(h,w)
##    am_s = beam
##    am_f = np.sqrt(pattern)
##    signal_s = am_s*np.exp(pm_s*1j)
##
##    for iteration in range(iterations):
##        signal_f = np.fft.fftshift(np.fft.fft2(np.fft.fftshift(signal_s)))
##        pm_f = np.angle(signal_f)
##        signal_f = am_f*np.exp(pm_f*1j)
##        signal_s = np.fft.ifftshift(np.fft.ifft2(np.fft.ifftshift(signal_f)))
##        pm_s = np.angle(signal_s)
##        signal_s = am_s*np.exp(pm_s*1j)
##
##    return pm_s

    # Advanced version, only on my computer (well, actually can be used on any as long as Nvidia card is used
def GS_algo(beam, pattern, pm_s, h, w, iterations):
    # Ensure inputs are in GPU memory
    beam = cp.asarray(beam)
    pattern = cp.asarray(pattern)
    pm_s = cp.asarray(pm_s)
    
    # Random phase matrix in the Fourier domain
    pm_f = cp.ones((h, w)) # Originally this is a random phase. We now just fix this to ones. 
    
    # Amplitude in spatial and Fourier domains
    am_s = beam
    am_f = cp.sqrt(pattern)
    
    # Initial signal in the spatial domain
    signal_s = am_s * cp.exp(pm_s * 1j)

    for iteration in range(iterations):
        # Forward Fourier Transform
        signal_f = cp.fft.fftshift(cp.fft.fft2(cp.fft.fftshift(signal_s)))
        pm_f = cp.angle(signal_f)
        signal_f = am_f * cp.exp(pm_f * 1j)
        
        # Inverse Fourier Transform
        signal_s = cp.fft.ifftshift(cp.fft.ifft2(cp.fft.ifftshift(signal_f)))
        pm_s = cp.angle(signal_s)
        signal_s = am_s * cp.exp(pm_s * 1j)

    # Ensure the output is back on CPU memory if needed
    pm_s = cp.asnumpy(pm_s)
    return pm_s

# Also from previous UROP work #
def lens_mask(diameter,f):

    wl = 0.78 * um
    M = 8*um
    f = f*mm
    diameter = diameter*M

    x0 = np.arange(0,1920)*M
    y0 = np.arange(0,1200)*M

    t0 = Scalar_mask_XY(x=x0,y=y0,wavelength = wl)
    t0.lens(r0=(960*M,600*M),radius=(diameter/2,diameter/2),focal=(f,f))

    t0.save_mask(rf'C:\Users\Zechidilin\Desktop\LensMask_{f}_{diameter}.bmp',kind='phase')
    lens = Image.open(rf'C:\Users\Zechidilin\Desktop\LensMask_{f}_{diameter}.bmp').convert('L')
    lens = np.asarray(lens,float)
    lens = 256*np.ones((1200,1920))-np.asarray(lens,float)
    lens_array = lens
##    plt.imshow(lens,cmap='gray')
##    plt.show()

    lens = Image.fromarray(lens).convert('L')
##    lens.save(rf'C:\Users\CaFMOT\Desktop\LensMask_{f}mm{diameter}um.bmp')
    return lens_array
    

def iiDGID(x,y,x0,y0,max_intensity,std):

    return max_intensity*np.exp(-((x-x0)**2+(y-y0)**2)/(2*(std**2)))


def pattern(nsites,intensity,std):
    background = np.zeros((1200,1920))
    site_x = []
    site_y = []
    for site in np.arange(nsites):
        x = int(input('x coordinate for this site: '))
        y = int(input('y coordinate for this site: '))
        site_x.append(x)
        site_y.append(y)

    x,y = np.meshgrid(np.arange(background.shape[1]),np.arange(background.shape[0]))
    for i in range(nsites):
        background += iiDGID(x,y,site_x[i],site_y[i],intensity,std)

    pattern_outcome = background
##    plt.imshow(pattern_outcome,cmap='coolwarm')
##    plt.show()
    return pattern_outcome

def rec_pattern(length,width,spacing,intensity,std):
    background = np.zeros((1200,1920))
    site_x = []
    site_y = []
    x,y = np.meshgrid(np.arange(background.shape[1]),np.arange(background.shape[0]))
    for i in range(length):
        for j in range(width):
            site_x.append(((960-(length-1)*spacing/2)+i*spacing)+30)
            site_y.append(((600-(length-1)*spacing/2)+j*spacing)-200) # Shift upwards
    site_y = [(y-600)/1.6+600 for y in site_y]
    for n in range(width*length):
        if std == 0:
            background[(int(site_y[n]),int(site_x[n]))]+=intensity
        else:
            background += iiDGID(x,y,site_x[n],site_y[n],intensity,std) # Gaussian. But seems like just specify certain points will be enough
    rec_pattern_outcome = background
##    plt.imshow(rec_pattern_outcome,cmap='coolwarm')
##    plt.show()
    return rec_pattern_outcome

def circ_pattern(radius,nsites,intensity,std):
    background = np.zeros((1200,1920))
    site_x = []
    site_y = []
    theta = 2*np.pi/nsites
    x,y = np.meshgrid(np.arange(background.shape[1]),np.arange(background.shape[0]))
    for i in range(nsites):
        site_x.append(np.cos((i+1)*theta)*radius+960)
        site_y.append(np.sin((i+1)*theta)*radius+600)
    site_y = [(y-600)/1.6+600 for y in site_y] # eliminates the elongation along y direction
    for n in range(nsites):
        if std != 0:
            background += iiDGID(x,y,site_x[n],site_y[n],intensity,std)
        else:
            background[(int(site_y[n]),int(site_x[n]))]+=intensity

    circ_pattern_outcome = background
##    plt.imshow(circ_pattern_outcome,cmap='coolwarm')
##    plt.show()
    return circ_pattern_outcome

def beam(intensity,std):
    background = np.zeros((1200,1920))
    x,y = np.meshgrid(np.arange(background.shape[1]),np.arange(background.shape[0]))
    background+=iiDGID(x,y,1920/2,1200/2,intensity,std)

    beam_outcome = background
##    plt.imshow(beam_outcome,cmap='coolwarm')
##    plt.show()
    return beam_outcome
    
def pmG_rec(length,width,spacing,intensity_s,std_s,intensity_f,std_f,diameter,f):
    begintime = time.time()
    pattern = rec_pattern(length,width,spacing,intensity_f,std_f)
    incident_beam = beam(intensity_s,std_s)
    pm_s = np.ones((1200,1920))
    phase_mask = GS_algo(incident_beam,pattern,pm_s,1200,1920,150)
    lens_phase_mask = lens_mask(diameter,f)
    lens_phase_mask = lens_phase_mask.astype('uint8')
    
##    plt.imshow(phase_mask,cmap='coolwarm')
##    plt.show()
    phase_mask_normalized = ((phase_mask-phase_mask.min())/(phase_mask.max()-phase_mask.min()))*255 # Or phase_mask - 0 / ... see which normalization works
    phase_mask_output = phase_mask_normalized.astype('uint8')
    overall_pm = ((phase_mask_normalized+lens_phase_mask)%256).astype(np.uint8)
##    plt.imshow(overall_pm,cmap='gray')
##    plt.show()

    path = rf'C:\Users\Zechidilin\OneDrive - Imperial College London\SLM Phase Masks\PhaseMask_{length}by{width}_{spacing}.bmp'
    path_overall_pm = rf'D:\Academic Files\Project 23-24\SLM Phase Mask\\PhaseMask_{length}by{width}_{spacing}.bmp'
##    imageio.imwrite(path,phase_mask_output)
    imageio.imwrite(path_overall_pm,overall_pm)
    endtime = time.time()
    duration = endtime-begintime
    print(f'Total duration for generating the phase mask: {duration} s')
    return duration

def pmG_circ(radius,nsites,intensity_s,std_s,intensity_f,std_f,diameter,f):
    begintime = time.time()
    pattern = circ_pattern(radius,nsites,intensity_f,std_f)
    incident_beam = beam(intensity_s,std_s)
    pm_s = np.ones((1200,1920))
    phase_mask = GS_algo(incident_beam,pattern,pm_s,1200,1920,100)
    lens_phase_mask = lens_mask(diameter,f)
    lens_phase_mask = lens_phase_mask.astype('uint8')
    
##    plt.imshow(phase_mask,cmap='coolwarm')
##    plt.show()
    phase_mask_normalized = ((phase_mask-phase_mask.min())/(phase_mask.max()-phase_mask.min()))*255
    phase_mask_output = phase_mask_normalized.astype('uint8')
    overall_pm = ((phase_mask_normalized+lens_phase_mask)%256).astype(np.uint8)
##    plt.imshow(overall_pm,cmap='gray')
##    plt.show()

##    path = rf'C:\Users\CaFMOT\Desktop\PhaseMask_{nsites}_radius{radius}.bmp'
    path_overall_pm = rf'D:\Academic Files\Project 23-24\SLM Phase Mask\\PhaseMaskwLens_{nsites}_radius{radius}.bmp'
##    imageio.imwrite(path,phase_mask_output)
    imageio.imwrite(path_overall_pm,overall_pm)
    endtime = time.time()
    duration = endtime-begintime
    print(f'Total duration for generating the phase mask: {duration} s')
    return duration

# Actually this can be used to generate arbitrary pattern, as long as you can draw it #
def Imperial_logo(image_path,intensity_s,std_s,diameter,f,name):
##    image_path = rf'C:\Users\CaFMOT\Desktop\Phase Masks\Blank.bmp'
    image = cv2.imread(image_path,cv2.IMREAD_GRAYSCALE)

    white_pixels = np.where(image == 255)

    coordinates = list(zip(white_pixels[1],white_pixels[0]))
    background = np.zeros((1200,1920))
    rows,cols = zip(*coordinates)
    rows = np.array(rows)-1
    cols = np.array(cols)-1

    background[cols,rows]=1
##    plt.imshow(background,cmap='gray')
##    plt.show()
##    background = np.fliplr(background)
##    background = np.flipud(background)
##    background = np.fliplr(background)
    Imperial_logo_outcome = background
    cv2.imwrite(r'C:\Users\Zechidilin\Desktop\background.bmp',background)

    
    begintime = time.time()
    pattern = Imperial_logo_outcome
    incident_beam = beam(intensity_s,std_s)
    pm_s = np.ones((1200,1920))
    phase_mask = GS_algo(incident_beam,pattern,pm_s,1200,1920,100)
    lens_phase_mask = lens_mask(diameter,f)
    lens_phase_mask = lens_phase_mask.astype('uint8')
    
    phase_mask_normalized = ((phase_mask-phase_mask.min())/(phase_mask.max()-phase_mask.min()))*255 # Or phase_mask - 0 / ... see which normalization works
    phase_mask_output = phase_mask_normalized.astype('uint8')
    overall_pm = ((phase_mask_normalized+lens_phase_mask)%256).astype(np.uint8)

##    path = rf'C:\Users\CaFMOT\Desktop\PhaseMask_Imperial.bmp'
    path_overall_pm = rf'D:\Academic Files\Project 23-24\SLM Phase Mask\{name}.bmp'
##    imageio.imwrite(path,phase_mask_output)
    imageio.imwrite(path_overall_pm,overall_pm)
    endtime = time.time()
    duration = endtime-begintime
    print(f'Total duration for generating the phase mask: {duration} s')
    return duration


class zoomable_label(QLabel):

    def __init__(self,parent=None):
        super(zoomable_label,self).__init__(parent)
        self.original_pixmap=None
        self.zoom_factor=1.0
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(640,480)
        self.offset = QPoint(0,0)

        
        self.last_mouse_position=None

    def setzoomablePixmap(self,pixmap):
        self.original_pixmap = pixmap
        self.updatePixmap()

    def wheelEvent(self,event):
        try:
            angle = event.angleDelta().y()
            if angle>0 and self.zoom_factor<=15:
                new_zoom_factor = self.zoom_factor*1.1
            elif angle<=0 and self.zoom_factor>0.1:
                new_zoom_factor = self.zoom_factor*0.9
            else:
                new_zoom_factor = self.zoom_factor

            cursor_position = event.position().toPoint()
            relative_position = (cursor_position+self.offset)/self.zoom_factor
            new_offset = (relative_position*new_zoom_factor)-cursor_position

            self.zoom_factor=  new_zoom_factor
            self.offset = new_offset
            self.updatePixmap()
        except Exception as error:
            print(f'{error}')
            traceback.print_exc()

    def mousePressEvent(self,event):
        try:
            if event.button()==Qt.LeftButton:
                self.last_mouse_position = event.globalPos()
        except Exception as error:
            print(f'{error}')
            traceback.print_exc()


    def mouseMoveEvent(self,event):
        try:
            if event.buttons()==Qt.LeftButton and self.last_mouse_position:
                delta = event.globalPos()-self.last_mouse_position
                self.last_mouse_position = event.globalPos()
                self.offset-=delta
                self.updatePixmap()
        except Exception as error:
            print(f'{error}')
            traceback.print_exc()

    def mouseReleaseEvent(self,event):
        self.last_mouse_position=None
        
    def updatePixmap(self):
        if self.original_pixmap is not None:
            new_size = self.original_pixmap.size()*self.zoom_factor
            scaled_pixmap = self.original_pixmap.scaled(new_size,Qt.KeepAspectRatioByExpanding)
##            self.setPixmap(scaled_pixmap)

            visible_pixmap = QPixmap(self.size())
            painter = QPainter(visible_pixmap)
##            painter.fillRect(visible_pixmap.rect(),Qt.black)

            draw_point = QPoint(-self.offset.x()+(self.width()-scaled_pixmap.width())//2,
                                -self.offset.y()+(self.height()-scaled_pixmap.height())//2)
            painter.drawPixmap(draw_point,scaled_pixmap)
            painter.end()
            self.setPixmap(visible_pixmap)


            
# UI. Make everything a bit clear #
class PMUI(QDialog):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Phase Mask Generator')
        self.setGeometry(300,400,1400,400)
        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        self.initUI()
        self.plot_windows=[]


    def initUI(self):
        generalUI = QHBoxLayout()

        self.text_panel = QTextEdit(self)
        self.text_panel.setReadOnly(True)

        generalUI.addWidget(self.text_panel)

        control_layout = QVBoxLayout()

        setup_layout = QHBoxLayout()
        
        col1 = QVBoxLayout()
        rec_label_layout = QHBoxLayout()
        rec_layout = QVBoxLayout()
        rec_dim_layout = QVBoxLayout()
        vlens_layout = QVBoxLayout()
        
        col2 = QVBoxLayout()
        circ_layout = QVBoxLayout()
        arb_pattern_layout = QVBoxLayout()

        buttons_layout = QVBoxLayout()
        self.default_button = QPushButton('Default Values')
        self.default_button.clicked.connect(self.default)
        self.generate_button = QPushButton('Generate Phase Mask')
        self.generate_button.clicked.connect(self.generate)
        self.clear_button = QPushButton('Clear')
        self.clear_button.clicked.connect(self.clear)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop)

        buttons_layout.addWidget(self.default_button)
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addWidget(self.stop_button)


        self.rec_label = QLabel('Rectangular Pattern')
        self.rec_check = QCheckBox(self)
        rec_label_layout.addWidget(self.rec_label)
        rec_label_layout.addWidget(self.rec_check)
        self.width_label = QLabel('Width')
        self.width_input = QLineEdit(self)
        self.width_input.setEnabled(False)
        self.rec_check.stateChanged.connect(lambda: self.width_input.setEnabled(self.rec_check.isChecked()))
        self.length_label = QLabel('Length')
        self.length_input = QLineEdit(self)
        self.length_input.setEnabled(False)
        self.rec_check.stateChanged.connect(lambda: self.length_input.setEnabled(self.rec_check.isChecked()))
        self.spacing_label = QLabel('Spacing')
        self.spacing_input = QLineEdit(self)
        self.spacing_input.setEnabled(False)
        self.rec_check.stateChanged.connect(lambda: self.spacing_input.setEnabled(self.rec_check.isChecked()))
        rec_dim_layout.addWidget(self.length_label)
        rec_dim_layout.addWidget(self.length_input)
        rec_dim_layout.addWidget(self.width_label)
        rec_dim_layout.addWidget(self.width_input)
        rec_dim_layout.addWidget(self.spacing_label)
        rec_dim_layout.addWidget(self.spacing_input)
        rec_layout.addLayout(rec_label_layout)
        rec_layout.addLayout(rec_dim_layout)
        col1.addLayout(rec_layout)

        self.v_lens_label = QLabel('Virtual Lens Setup')
        self.v_lens_diameter_label = QLabel('Virtual Lens Diameter')
        self.v_lens_diameter_input = QLineEdit(self)
        self.v_lens_f_label = QLabel('Virtual Lens Focal Length / mm')
        self.v_lens_f_input = QLineEdit(self)
        vlens_layout.addWidget(self.v_lens_label)
        vlens_layout.addWidget(self.v_lens_diameter_label)
        vlens_layout.addWidget(self.v_lens_diameter_input)
        vlens_layout.addWidget(self.v_lens_f_label)
        vlens_layout.addWidget(self.v_lens_f_input)
        col1.addLayout(vlens_layout)

        setup_layout.addLayout(col1)

        circ_label_layout = QHBoxLayout()
        self.circ_label = QLabel('Circular Pattern')
        self.circ_check = QCheckBox(self)
        circ_label_layout.addWidget(self.circ_label)
        circ_label_layout.addWidget(self.circ_check)
        self.nsites_label = QLabel('Number of Sites')
        self.nsites_input = QLineEdit(self)
        self.nsites_input.setEnabled(False)
        self.circ_check.stateChanged.connect(lambda: self.nsites_input.setEnabled(self.circ_check.isChecked()))
        self.radius_label = QLabel('Radius')
        self.radius_input = QLineEdit(self)
        self.radius_input.setEnabled(False)
        self.circ_check.stateChanged.connect(lambda: self.radius_input.setEnabled(self.circ_check.isChecked()))
        circ_layout.addLayout(circ_label_layout)
        circ_layout.addWidget(self.nsites_label)
        circ_layout.addWidget(self.nsites_input)
        circ_layout.addWidget(self.radius_label)
        circ_layout.addWidget(self.radius_input)
        col2.addLayout(circ_layout)

        arb_pattern_label_layout = QHBoxLayout()
        self.arb_pattern_label = QLabel('Arbitrary Pattern')
        self.arb_pattern_check = QCheckBox(self)
        arb_pattern_label_layout.addWidget(self.arb_pattern_label)
        arb_pattern_label_layout.addWidget(self.arb_pattern_check)
        self.arb_pattern_file = QPushButton('Select the pattern image')
        self.arb_pattern_file.setEnabled(False)
        self.arb_pattern_check.stateChanged.connect(lambda: self.arb_pattern_file.setEnabled(self.arb_pattern_check.isChecked()))
        self.arb_pattern_file.clicked.connect(self.file_selection)
        self.arb_pattern_path = QLineEdit(self)
        self.arb_pattern_path.setEnabled(False)
        self.arb_pattern_check.stateChanged.connect(lambda: self.arb_pattern_path.setEnabled(self.arb_pattern_check.isChecked()))
        self.arb_pattern_path_label = QLabel('Path of Pattern')
        self.arb_pattern_name = QLabel('Name your pattern')
        self.arb_pattern_name_input = QLineEdit(self)
        self.arb_pattern_name_input.setEnabled(False)
        self.arb_pattern_check.stateChanged.connect(lambda: self.arb_pattern_name_input.setEnabled(self.arb_pattern_check.isChecked()))
        arb_pattern_layout.addLayout(arb_pattern_label_layout)
        arb_pattern_layout.addWidget(self.arb_pattern_path_label)
        arb_pattern_layout.addWidget(self.arb_pattern_file)
        arb_pattern_layout.addWidget(self.arb_pattern_path)
        arb_pattern_layout.addWidget(self.arb_pattern_name)
        arb_pattern_layout.addWidget(self.arb_pattern_name_input)
        col2.addLayout(arb_pattern_layout)


        setup_layout.addLayout(col2)

        control_layout.addLayout(setup_layout)

        s_layout = QHBoxLayout()
        s_sub_layout_1 = QVBoxLayout()
        self.s_int_label = QLabel('Source Intensity')
        self.s_int_input = QLineEdit(self)
        self.s_std_label = QLabel('Source Standard Deviation')
        self.s_std_input = QLineEdit(self)
        s_sub_layout_1.addWidget(self.s_int_label)
        s_sub_layout_1.addWidget(self.s_int_input)
        s_sub_layout_1.addWidget(self.s_std_label)
        s_sub_layout_1.addWidget(self.s_std_input)

        s_sub_layout_2 = QVBoxLayout()
        self.f_int_label = QLabel('FP Intensity')
        self.f_int_input = QLineEdit(self)
        self.f_std_label = QLabel('FP Standard Deviation')
        self.f_std_input = QLineEdit(self)
        s_sub_layout_2.addWidget(self.f_int_label)
        s_sub_layout_2.addWidget(self.f_int_input)
        s_sub_layout_2.addWidget(self.f_std_label)
        s_sub_layout_2.addWidget(self.f_std_input)

        s_layout.addLayout(s_sub_layout_1)
        s_layout.addLayout(s_sub_layout_2)

        crop_layout = QHBoxLayout()

        img_crop_x_layout = QVBoxLayout()
        self.crop_x_label = QLabel('Image Cropping Start Row')
        self.crop_x_input = QLineEdit(self)
        img_crop_x_layout.addWidget(self.crop_x_label)
        img_crop_x_layout.addWidget(self.crop_x_input)

        img_crop_y_layout = QVBoxLayout()
        self.crop_y_label = QLabel('Image Cropping Start Col')
        self.crop_y_input = QLineEdit(self)
        img_crop_y_layout.addWidget(self.crop_y_label)
        img_crop_y_layout.addWidget(self.crop_y_input)

        crop_layout.addLayout(img_crop_x_layout)
        crop_layout.addLayout(img_crop_y_layout)

        control_layout.addLayout(s_layout)
        control_layout.addLayout(crop_layout)
        control_layout.addLayout(buttons_layout)
        

        generalUI.addLayout(control_layout)

        camera_control = QVBoxLayout()

        self.camera_label = QLabel('Camera')
        self.nphotos_label = QLabel('Number of Photos Taken')
        self.nphotos_input = QLineEdit(self)
        self.expt_label = QLabel('Exposure Time / us')
        self.expt_input = QLineEdit(self)
        self.heading_label = QLabel('Heading of Photos')
        self.heading_input = QLineEdit(self)
        self.image_path_label = QLabel('Path for Saved Images')
        self.image_path_button = QPushButton('Select a Path')
        self.image_path_button.clicked.connect(self.path_selection)
        self.image_path_input = QLineEdit(self)
        self.image_path_input.setReadOnly(True)
        self.ref_image_selection_button = QPushButton('Select a Ref Image')
        self.ref_image_selection_button.clicked.connect(self.ref_image_selection)
        self.ref_image_selection = QLineEdit(self)
        self.image_path_input.setReadOnly(True)
        self.take_photo = QPushButton('Take Photos')
        self.take_photo.clicked.connect(self.cam_start)
        self.adaptive_algo_label = QLabel('Intensity Equalisation')
        self.adaptive_algo_iteration_label = QLabel('Iterations')
        self.adaptive_algo_iteration_input = QLineEdit(self)
        self.adaptive_algo_start = QPushButton('Equalise Intensities')
        self.adaptive_algo_start.clicked.connect(self.intensity_equalisation)
        self.calibration_button = QPushButton('SLM Calibration')
        self.calibration_button.clicked.connect(self.SLM_calibration)
        G_layout = QHBoxLayout()
        self.G_label = QLabel('G-factor')
        self.G_input = QLineEdit(self)
        G_layout.addWidget(self.G_label)
        G_layout.addWidget(self.G_input)
        self.pm_path_button = QPushButton('Select a Phase Mask')
        self.pm_path_button.clicked.connect(self.PM_selection)
        self.pm_path_input = QLineEdit(self)
        
        camera_control.addWidget(self.camera_label)
        camera_control.addWidget(self.nphotos_label)
        camera_control.addWidget(self.nphotos_input)
        camera_control.addWidget(self.expt_label)
        camera_control.addWidget(self.expt_input)
        camera_control.addWidget(self.heading_label)
        camera_control.addWidget(self.heading_input)
        camera_control.addWidget(self.image_path_label)
        camera_control.addWidget(self.image_path_button)
        camera_control.addWidget(self.image_path_input)
        camera_control.addWidget(self.adaptive_algo_label)
        camera_control.addLayout(G_layout)
        camera_control.addWidget(self.ref_image_selection_button)
        camera_control.addWidget(self.ref_image_selection)
        camera_control.addWidget(self.adaptive_algo_iteration_label)
        camera_control.addWidget(self.adaptive_algo_iteration_input)
        camera_control.addWidget(self.pm_path_button)
        camera_control.addWidget(self.pm_path_input)
        camera_control.addWidget(self.adaptive_algo_start)
        camera_control.addWidget(self.calibration_button)
        camera_control.addWidget(self.take_photo)

        camera_streaming = QVBoxLayout()
        self.camera_streaming_label = QLabel('Camera Stream')
        self.stream_panel = zoomable_label()
        self.stream_panel.setPixmap(QPixmap(r"C:\Users\CaFMOT\Desktop\imgs\stream_background.tif"))
        self.stream_start_button = QPushButton('Start Streaming')
        self.stream_start_button.clicked.connect(self.CamStream)
        self.stream_stop_button = QPushButton('Stop Streaming')
        self.stream_stop_button.clicked.connect(self.StopStream)

        camera_streaming.addWidget(self.camera_streaming_label)
        camera_streaming.addWidget(self.stream_panel)
        camera_streaming.addWidget(self.stream_start_button)
        camera_streaming.addWidget(self.stream_stop_button)
        
        
        
        
        generalUI.addLayout(camera_control)
        generalUI.addLayout(camera_streaming)

        self.setLayout(generalUI)

    def intensity_equalisation(self):
        try:
            self.nphotos_input.setText('1')
            iterations = int(self.adaptive_algo_iteration_input.text())
            image_path = self.image_path_input.text()
            heading =  self.heading_input.text()
            G = float(self.G_input.text())
            ref_path = self.ref_image_selection.text()
            pm_path = self.pm_path_input.text()
            start_row = int(self.crop_x_input.text())
            start_col = int(self.crop_y_input.text())
            num_regions = int(self.width_input.text())
            length = int(self.length_input.text())
            width = int(self.width_input.text())
            self.text_panel.append('Initialising equalisation sequence')
            self.text_panel.append(f'Current adaptive gain factor: G = {G}')
            self.equalisation_thread = intthread(image_path,iterations,heading,G,ref_path,pm_path,start_row,start_col,num_regions,length,width)
            self.equalisation_thread.iterationend.connect(self.iteration_finished)
            self.equalisation_thread.intend.connect(self.int_finished, type=Qt.QueuedConnection)
            self.equalisation_thread.image_acq.connect(self.image_acquisition)
            self.equalisation_thread.maskend.connect(self.maskfinished)
            self.equalisation_thread.start()
        except Exception as error:
            self.text_panel.append(f'Intensity equalisation error: {error}')

    def SLM_calibration(self):
        try:
            image_path = self.image_path_input.text()
            start_row = int(self.crop_x_input.text())
            start_col = int(self.crop_y_input.text()) 
            self.text_panel.append('Scanning 0th-order intensities...')
            self.calibration_thread = calibrationthread(image_path,start_row,start_col)
            self.calibration_thread.calibend.connect(self.calibration_finished)
            self.calibration_thread.img_acq.connect(self.calibration_image_acquisition)
            self.calibration_thread.start()
        except Exception as error:
            self.text_panel.append(f'Calibration error:{error}')

    def calibration_finished(self):
        self.text_panel.append('Calibration has finished. New LUT file saved to...')
        if self.calibration_thread and self.calibration_thread.isRunning():
            self.calibration_thread.terminate()

    def iteration_finished(self,mean_intensity,actual_mean_intensity,intensity_std,iteration,percentage,actual_max,actual_min):
        try:
            image_path = self.image_path_input.text()
            heading =  self.heading_input.text()
            self.text_panel.append('')
            self.text_panel.append('---------------------------')
            self.text_panel.append(f'Current iteration: {iteration}')
            self.text_panel.append(f'Current reference mean intensity:{mean_intensity}')
            self.text_panel.append(f'Actual mean intensity:{actual_mean_intensity},std:{intensity_std}')
            self.text_panel.append(f'Deviation: {round(percentage*100,2)}'+'%')
            self.text_panel.append(f'Maximum intensity is {round(actual_max/actual_mean_intensity,3)*100}'+'% of the mean')
            self.text_panel.append(f'Minimum intensity is {round(actual_min/actual_mean_intensity,3)*100}'+'% of the mean')
            self.text_panel.append('Generating a new phase mask for updated intensity conditions')
            self.text_panel.append('---------------------------')
            self.text_panel.append('')
##            pixmap = QPixmap.fromImage(rf'{image_path}\{heading}_iteration{iteration}.tif')
##            self.stream_panel.setPixmap(pixmap)
        except Exception as error:
            self.text_panel.append(f'Iteration finished error:{error}')


    def calibration_image_acquisition(self,num):
        try:
            self.heading_input.setText(f'{num}')
            self.take_photo.click()
        except Exception as error:
            print(error)

    @pyqtSlot(list,list,list,list)
    def int_finished(self, Mean, std, itr, percent):
        try:
            self.equalisation_thread.terminate()
            self.text_panel.append('Equalisation process has been terminated')
            self.text_panel.append(f'Mean:{Mean}')
            self.text_panel.append(f'Standard deviation: {std}')
            self.text_panel.append(f'Deviation: {percent}')
            # First plot (Mean and Standard Deviation)
            self.figure1 = Figure()
            self.canvas1 = FigureCanvas(self.figure1)
            ax1 = self.figure1.add_subplot(111)
            ax1.clear()
            ax1.plot(itr, Mean, linestyle='-', color='r', label='Mean')
            ax1.plot(itr, std, linestyle='-', color='b', label='Standard Deviation')
            ax1.set_xlabel('Iteration')
            ax1.set_ylabel('Values')
            ax1.legend()
            self.create_popup_window(self.canvas1, "Mean and Standard Deviation")

            # Second plot (Percentage)
            self.figure2 = Figure()
            self.canvas2 = FigureCanvas(self.figure2)
            ax2 = self.figure2.add_subplot(111)
            ax2.clear()
            ax2.plot(itr, percent, linestyle='-', color='black', label='Deviation')
            ax2.set_xlabel('Iteration')
            ax2.set_ylabel('Percentage' + '%')
            ax2.legend()
            self.create_popup_window(self.canvas2, "Deviation")
            

        except Exception as error:
            print(error) 

    def create_popup_window(self, canvas, title):
        # Create a new window for each plot
        window = QMainWindow()
        window.setWindowTitle(title)
        window.setCentralWidget(canvas)
        toolbar = NavigationToolbar(canvas, window)
        window.addToolBar(toolbar)
        window.resize(800, 600)
        window.show()

        # Save a reference to the window to prevent it from being garbage collected
        self.plot_windows.append(window)


    def maskfinished(self,itr,std):
        self.text_panel.append('New phase mask has been generated and sent to the server machine')

    def default(self):
        try:
            self.crop_x_input.setText('236')
            self.crop_y_input.setText('413')
            self.length_input.setText('4')
            self.width_input.setText('4')
            self.v_lens_diameter_input.setText('4000')
            self.v_lens_f_input.setText('200')
            self.nsites_input.setText('12')
            self.radius_input.setText('40')
            self.s_int_input.setText('100')
            self.s_std_input.setText('1275')
            self.f_int_input.setText('20')
            self.f_std_input.setText('0')
            self.spacing_input.setText('30')
            self.arb_pattern_path.setText(rf'C:\Users\CaFMOT\Desktop\Phase Masks\Blank.bmp')
            self.expt_input.setText('25')
            self.nphotos_input.setText('1')
            self.image_path_input.setText(rf'D:\Academic Files\Project 23-24\SLM Images')
            self.ref_image_selection.setText(rf'D:\Academic Files\Project 23-24\SLM Images\5by5.bmp')
            self.adaptive_algo_iteration_input.setText('0')
            self.heading_input.setText('4by4')
            self.G_input.setText('0.2')
            self.pm_path_input.setText(rf'D:\Academic Files\Project 23-24\SLM Phase Mask\PhaseMask_4by4_30_sint100_fint20.bmp')
        except Exception as error:
            self.text_panel.append(f'{error}')

    def generate(self):
        
        try:
            if self.rec_check.isChecked() and not self.circ_check.isChecked() and not self.arb_pattern_check.isChecked():
                length = int(self.length_input.text())
                width = int(self.width_input.text())
                spacing = int(self.spacing_input.text())
                s_int = float(self.s_int_input.text())
                s_std = int(self.s_std_input.text())
                f_int = float(self.f_int_input.text())
                f_std = float(self.f_std_input.text())
                diameter = int(self.v_lens_diameter_input.text())
                f = int(self.v_lens_f_input.text())
                self.rec_thread = recthread(length,width,spacing,s_int,s_std,f_int,f_std,diameter,f)
                self.rec_thread.start()
                self.rec_thread.recthreadend.connect(self.threadfinished)
                self.text_panel.append('Generating a rectangular pattern...')
                
            elif self.circ_check.isChecked() and not self.rec_check.isChecked() and not self.arb_pattern_check.isChecked():
                nsites = int(self.nsites_input.text())
                radius = int(self.radius_input.text())
                s_int = int(self.s_int_input.text())
                s_std = int(self.s_std_input.text())
                f_int = int(self.f_int_input.text())
                f_std = int(self.f_std_input.text())
                diameter = int(self.v_lens_diameter_input.text())
                f = int(self.v_lens_f_input.text())
                self.circ_thread = circthread(radius,nsites,s_int,s_std,f_int,f_std,diameter,f)
                self.circ_thread.start()
                self.circ_thread.circthreadend.connect(self.threadfinished)
                self.text_panel.append('Generating a circular pattern...')

            elif self.arb_pattern_check.isChecked() and not self.rec_check.isChecked() and not self.circ_check.isChecked():
                image_path = str(self.arb_pattern_path.text())
                s_int = int(self.s_int_input.text())
                s_std = int(self.s_std_input.text())
                name = str(self.arb_pattern_name_input.text())
                diameter = int(self.v_lens_diameter_input.text())
                f = int(self.v_lens_f_input.text())
                self.arb_pattern_thread = arbpatternthread(image_path,s_int,s_std,diameter,f,name)
                self.arb_pattern_thread.start()
                self.arb_pattern_thread.arbpatternthreadend.connect(self.threadfinished)
                self.text_panel.append('Generating a designated pattern...')


            else:
                self.text_panel.append('Wrong pattern selection. One and only one type of pattern is allowed at one time')

        except Exception as error:
            self.text_panel.append(f'Generation error:{error}')



    def clear(self):
        self.text_panel.clear()

    def stop(self):
        try:
            if self.equalisation_thread and self.equalisation_thread.isRunning():
                self.equalisation_thread.terminate()
                self.text_panel.append('Equalisation process has been stopped')
            elif self.stream_thread and self.stream_thread.isRunning():
                self.stream_thread.terminate()
                self.text_panel.append('Camera Streaming thread has been stopped')
            else:
                self.text_panel.append('No active working threads at the moment')
        except Exception as error:
            self.text_panel.append(f'{error}')

    def image_acquisition(self,iteration,heading):
        try:
            self.heading_input.setText(f'{heading}_iteration{iteration}')
            self.take_photo.click()
        except Exception as error:
            self.text_panel.append(f'Image acquisition signal error:{error}')

    def threadfinished(self,duration,pm_type):
        try:
            if pm_type == 0:
                self.rec_thread.terminate()
            elif pm_type == 1:
                self.circ_thread.terminate()
            else:
                self.arb_pattern_thread.terminate()
        except Exception as error:
            self.text_panel.append(f'Thread finished error:{error}')
        self.text_panel.append(f'Phase mask generated and saved to Desktop\Phase Mask. Total duration: {duration} s')

    def file_selection(self):
        try:
            
            options = QFileDialog.Options()
            filename,_ = QFileDialog.getOpenFileName(self,'Select a file ','','All Files (*);;bmp files (*.bmp)',options = options)

            if filename:
                self.arb_pattern_path.setText(filename)

        except Exception as error:

            self.text_panel.append(f'{error}')

    def PM_selection(self):
        try:
            
            options = QFileDialog.Options()
            filename,_ = QFileDialog.getOpenFileName(self,'Select a file ','','All Files (*);;bmp files (*.bmp)',options = options)

            if filename:
                self.pm_path_input.setText(filename)

        except Exception as error:

            self.text_panel.append(f'{error}')

    def ref_image_selection(self):
        try:
            
            options = QFileDialog.Options()
            filename,_ = QFileDialog.getOpenFileName(self,'Select a pattern file ','','All Files (*);;bmp files (*.bmp)',options = options)

            if filename:
                self.ref_image_selection.setText(filename)

        except Exception as error:

            self.text_panel.append(f'{error}')

    def path_selection(self):
        try:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            directoryname  = QFileDialog.getExistingDirectory(self,'Select a directory','',options=options)
            if directoryname:
                self.image_path_input.setText(directoryname)
        except Exception as error:
            self.text_panel.append(f'Camera start error: {error}')

    def cam_start(self):
        try:
            nphotos = int(self.nphotos_input.text())
            exptime = float(self.expt_input.text())
            heading = self.heading_input.text()
            image_path = self.image_path_input.text()
            self.text_panel.append('Acquiring photo frames...')
            self.camera_thread = camerathread(nphotos,exptime,heading,image_path)
            self.camera_thread.cameraend.connect(self.camera_finished)
            self.camera_thread.start()

        except Exception as error:
            self.text_panel.append(f'Camera start error: {error}')

    def camera_finished(self):
        self.text_panel.append('Images have been successfully acquired')

    def CamStream(self):
        try:
            exptime = float(self.expt_input.text())
            self.stream_thread = CamStreamThread(exptime)
            self.stream_thread.stream_frame.connect(self.update_frame)
            self.stream_thread.start()
            self.stream_stop_button.setEnabled(True)
            self.stream_start_button.setEnabled(False)
            self.take_photo.setEnabled(False)
        except Exception as error:
            print(f'Cam Stream error: {error}')

    def update_frame(self,pixmap):
##        self.stream_panel.setPixmap(pixmap)
        try:
            self.stream_panel.setzoomablePixmap(pixmap)
        except Exception as error:
            print(f'Update frame error: {error}')

    def StopStream(self):
        try:
            self.nphotos = 0
            self.exptime = 0
            command = str([self.nphotos,self.exptime,2])
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.connect((server_ip,12345))
                s.sendall(command.encode())
                received_data = b''
                while True:
                    packet = s.recv(1000)
                    if not packet:
                        break
                    received_data += packet
                    break
                feedback = pickle.loads(received_data)
                print(len(feedback))
                while feedback == 'n':
                    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                        s.connect((server_ip,12345))
                        s.sendall(command.encode())
                        received_data = b''
                        while True:
                            packet = s.recv(1000)
                            if not packet:
                                break
                            received_data += packet
                            break
                        feedback = pickle.loads(received_data)
                        print(len(feedback))
            self.stream_stop_button.setEnabled(False)
            self.stream_start_button.setEnabled(True)
            self.take_photo.setEnabled(True)
        except Exception as error:
            self.text_panel.append(f'Stop Stream error: {error}')
            pass
        
class recthread(QThread):
    recthreadend = pyqtSignal(float,int)

    def __init__(self,length,width,spacing,s_int,s_std,f_int,f_std,diameter,f):
        super().__init__()
        self.length = length
        self.width = width
        self.spacing = spacing
        self.s_int = s_int
        self.s_std = s_std
        self.f_int = f_int
        self.f_std = f_std
        self.diameter = diameter
        self.f = f

    def run(self):
        try:
            duration = pmG_rec(self.length,self.width,self.spacing,self.s_int,\
                               self.s_std,self.f_int,self.f_std,self.diameter,self.f)
            pm_type=0
            self.recthreadend.emit(duration,pm_type)
        except Exception as error:
            print(f'{error}')

class circthread(QThread):
    circthreadend =  pyqtSignal(float,int)

    def __init__(self,radius,nsites,s_int,s_std,f_int,f_std,diameter,f):
        super().__init__()
        self.radius = radius
        self.nsites = nsites
        self.s_int = s_int
        self.s_std = s_std
        self.f_int = f_int
        self.f_std = f_std
        self.diameter = diameter
        self.f = f

    def run(self):
        duration = pmG_circ(self.radius,self.nsites,self.s_int,self.s_std,\
                            self.f_int,self.f_std,self.diameter,self.f)
        pm_type = 1
        self.circthreadend.emit(duration,pm_type)

class arbpatternthread(QThread):
    arbpatternthreadend = pyqtSignal(float,int)

    def __init__(self,image_path,s_int,s_std,diameter,f,name):
        super().__init__()
        self.image_path = image_path
        self.s_int = s_int
        self.s_std = s_std
        self.diameter = diameter
        self.f = f
        self.name = name

    def run(self):
        duration = Imperial_logo(self.image_path,self.s_int,self.s_std,self.diameter,self.f,self.name)
        pm_type=2
        self.arbpatternthreadend.emit(duration,pm_type)

    
class camerathread(QThread):
    cameraend = pyqtSignal()

    def __init__(self,nphotos,exptime,heading,image_path):
        super().__init__()
        self.nphotos = nphotos
        self.exptime = exptime
        self.heading = heading
        self.image_path = image_path

    def run(self):
        try:
            images = send_command(server_ip,str([self.nphotos,self.exptime,0]),self.nphotos)
            print('Images received')
            outputpath = rf'{self.image_path}'
            os.makedirs(outputpath,exist_ok=True)
            if self.nphotos ==1:
                image_array =  images
                filename = f'{self.heading}.tif'
                filepath = os.path.join(outputpath,filename)
                tiff.imwrite(filepath,image_array)
            if self.nphotos>1:
                for i, image_array in enumerate(images):
                    filename = f'{self.heading}_{i}.tif'
                    filepath = os.path.join(outputpath,filename)
                    tiff.imwrite(filepath,image_array)

            self.cameraend.emit()
        except Exception as error:
            print(f'Camera thread error: {error}')


n = 5
input_shape = np.array(2+n*n,)


class intthread(QThread):
    iterationend = pyqtSignal(float,float,float,int,float,float,float)
    image_acq = pyqtSignal(int,str)
    intend = pyqtSignal(list,list,list,list)
    maskend = pyqtSignal(list,list)

    def __init__(self,image_path,iterations,heading,G,ref_path,pm_path,start_row,start_col,num_regions,length,width):
        super().__init__()
        self.image_path = image_path
        self.iterations = iterations
        self.heading = heading
        self.G = G
        self.ref_path = ref_path
        self.pm_path = pm_path
        self.start_row = start_row
        self.start_col = start_col
        self.num_regions = num_regions
        self.length = length
        self.width = width

    def run(self):
        try:
            heading = self.heading
            ref_path = rf'{self.ref_path}'
            path_88 = rf'{self.pm_path}'
            print(path_88)
            results = image_intensity(ref_path,self.start_row,self.start_col,self.num_regions)
            mean_intensity = results[1]
            std_threshold = 2
            ref_intensity_array_2D = results[0]
            length = self.length
            width = self.width
            output_shape = (width,length)
            intensity_s = 255 # 1
            std_s = 1275 #180
            intensity = 255 #intensity_s/(length*width) # 20
            Mean = []
            std = []
            itr = []
            percent = []
            prev_normalised_intensity_array_2D = np.ones((length,width))

            feedback = send_phase_mask(server_ip,path_88)
            print(feedback)
            while feedback == '0':
                feedback = send_phase_mask(server_ip,path_88)
            if self.iterations != 0:
                for iteration in range(self.iterations):

                    
                    # Image acquisition and analysis#
                    #-------------------------------#
                    self.image_acq.emit(iteration,heading)
                    time.sleep(1) # Wait for the image to be acquired
                    image_path = rf'{self.image_path}\{heading}_iteration{iteration}.tif'
                    # Obtained intensity
                    intensity_array_2D = image_intensity(image_path,self.start_row,self.start_col,self.num_regions)[0]
                    actual_max = np.max(intensity_array_2D)
                    actual_min = np.min(intensity_array_2D)
                    print(intensity_array_2D)
                    actual_mean_intensity = image_intensity(image_path,self.start_row,self.start_col,self.num_regions)[1]
                    intensity_std = image_intensity(image_path,self.start_row,self.start_col,self.num_regions)[2]

                    #-------------------------------------------------------------------------------------------------------------------# 
                    # Updated algorithm (04/04/2024)--- calculate, then normalise with respect to the ref image's mean intensity
                    intensity_array_2D_iterated = actual_mean_intensity/(1-self.G*(1-intensity_array_2D/actual_mean_intensity)) # 0418 update: change mean_intensity to actual_mean_intensity
                    normalised_intensity_array_2D = (intensity_array_2D_iterated/mean_intensity)*prev_normalised_intensity_array_2D # Original algorithm was done without np.sqrt
                    prev_normalised_intensity_array_2D = normalised_intensity_array_2D
                    summation = np.sum(normalised_intensity_array_2D)
                    normalised_intensity_array_2D = normalised_intensity_array_2D/summation # 0419 update: normalise wrt to summation
                    print(f'After algorithm: {normalised_intensity_array_2D},sum is {np.sum(normalised_intensity_array_2D)}')
                    #-------------------------------------------------------------------------------------------------------------------#
                    
                    background = np.zeros((1200,1920))
                    spacing = 30
                    site_x = []
                    site_y = []
                    x,y = np.meshgrid(np.arange(background.shape[1]),np.arange(background.shape[0]))
                    for i in range(length):
                        for j in range(width):
                            site_x.append(((960-(length-1)*spacing/2)+i*spacing)+30)
                            site_y.append(((600-(length-1)*spacing/2)+j*spacing)-200)
                    site_y = [(y-600)/1.6+600 for y in site_y]
                    spots=[]
                    for n in range(length*width):
                        background[(int(site_y[n]),int(site_x[n]))]+=intensity*normalised_intensity_array_2D[n//length,n%width]
                        
                    mean_intensity = round(mean_intensity,3)
                    actual_mean_intensity = round(actual_mean_intensity,3)
                    Mean.append(actual_mean_intensity)
                    intensity_std = round(intensity_std,3)
                    percentage = round(intensity_std/actual_mean_intensity,3)
                    G1 = min(5*(percentage**2),0.8) # Dynamic gain factor --- quadratic
##                    self.G = min(np.exp(5*(percentage**2))-1,1) # Dynamic gain --- exponential, terrible
                    G2=  25*(percentage**3) # Can also be made cubic or whatever
                    G3 = 2066.1157*(percentage**5) # quintic
##                    G4 = 227.27*(percentage**4) # quartic
##                    G4 = 25*(percentage**3) # cubic
                    G4 = 2.75*(percentage**2) # quadratic
                    
                    #Initially: quadratic. 0422: conditional quadratic, cubic, and quintic.
                    # Conditional dynamic G
                    if percentage < 0.2 and percentage >= 0.11:
                        self.G = G2
                    elif percentage > 0 and percentage < 0.11: # Seems to be the most tricky part
                        self.G = G3
                    else:
                        self.G = G1
                    percent.append(percentage)
                    std.append(intensity_std)
                    self.iterationend.emit(mean_intensity,actual_mean_intensity,intensity_std,iteration,percentage,actual_max,actual_min)
                    pattern = background
                    incident_beam = beam(intensity_s,std_s)
                    pm_s = np.ones((1200,1920))
                    phase_mask = GS_algo(incident_beam,pattern,pm_s,1200,1920,150)
                    lens_phase_mask = lens_mask(4000,200)                                   
                    lens_phase_mask = lens_phase_mask.astype('uint8')

                    phase_mask_normalized = ((phase_mask-phase_mask.min())/(phase_mask.max()-phase_mask.min()))*255
                    phase_mask_output = phase_mask_normalized.astype('uint8')
                    overall_pm = ((phase_mask_normalized+lens_phase_mask)%256).astype(np.uint8)
                    
                    path_overall_pm = rf'D:\Academic Files\Project 23-24\SLM Phase Mask\PhaseMaskwLens_8by8_iteration{self.iterations}.bmp'
                    imageio.imwrite(path_overall_pm,overall_pm)
                    feedback = send_phase_mask(server_ip,path_overall_pm)
                    while feedback == '0':
                        feedback = send_phase_mask(server_ip,path_overall_pm)
                    self.maskend.emit(itr,std)
                    itr.append(iteration)
                self.intend.emit(Mean,std,itr,percent)
                time.sleep(1)
                              
            else:
                print('Initial pattern has been fed to the SLM')
                
                
        except Exception as error:
            print(f'Equalisation thread error: {error}')
            traceback.print_exc()
            pass

class calibrationthread(QThread):
    calibend = pyqtSignal()
    img_acq = pyqtSignal(int)

    def __init__(self,image_path,start_row,start_col):
        super().__init__()
        self.image_path = image_path
        self.start_row = start_row
        self.start_col = start_col

    def run(self):
        try:
            num_list = np.linspace(0,255,256)
            intensity_list = []
            output_csv = rf'D:\Academic Files\Project 23-24\SLM Calibration\output csv\Raw0.csv'
            for num in range(256):
                pm_path = rf'D:\Academic Files\Project 23-24\SLM Calibration\Stripes\stripes_{num}.bmp'
                feedback = send_phase_mask(server_ip,pm_path)
                while feedback == '0':
                    feedback = send_phase_mask(server_ip,pm_path)
                self.img_acq.emit(num)
                time.sleep(1.0)
                img_path = rf'{self.image_path}\{num}.tif'
                image = cv2.imread(img_path,cv2.IMREAD_GRAYSCALE)
                image = image[self.start_row:self.start_row+8,self.start_col:self.start_col+8]
                slice_path = rf'D:\Academic Files\Project 23-24\SLM Calibration\calibration slices\{num}_slice.bmp'
                cv2.imwrite(slice_path,image)
                x_int=  []
                y_int = []
                for i in range(8):
                    row_int = 0
                    for j in range(8):
                        row_int+=image[i,j]
                    row_int=  row_int/8*1.23

                    x_int.append(row_int)

                for j in range(8):
                    col_int = 0
                    for i in range(8):
                        col_int+=image[i,j]
                    col_int = col_int/8*1.4
                    y_int.append(col_int)
                intensity = (max(x_int)+max(y_int))/2+0.00018
                intensity_list.append(intensity)
            with open(output_csv,'w',newline='') as file:
                writer = csv.writer(file)

                for num, intensity in zip(num_list,intensity_list):
                    writer.writerow([num,intensity])
            self.calibend.emit()
        except Exception as error:
            print(f'calibration thread error: {error}')
            traceback.print_exc()
                
class CamStreamThread(QThread):
    stream_frame = pyqtSignal(QPixmap)
    
    def __init__(self,exptime):
        super().__init__()
        self.exptime = exptime

    def run(self):
        try:
            self.nphotos = 0
            command = str([self.nphotos,self.exptime,1])
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.connect(('155.198.206.58',12345))
                s.sendall(command.encode())

                while True:
                    data_length = int.from_bytes(s.recv(4),byteorder='big')
                    data_buffer = b''
                    while len(data_buffer)<data_length:
                        data_buffer+=s.recv(data_length-len(data_buffer))
                    image_frame = pickle.loads(data_buffer)
                    height,width = image_frame.shape
                    acquired_frame = QImage(image_frame.data,width,height,width,QImage.Format_Grayscale8)
                    pixmap = QPixmap.fromImage(acquired_frame)
                    self.stream_frame.emit(pixmap)
        except Exception as err:
            print(f"Camera streaming error: {err}")
            traceback.print_exc()

def diffraction_gratings():
    try:
        background = 255*np.ones((1200,1920))
        WFC_path = r'D:\Academic Files\Project 23-24\Meadowlark Optics\Blink 1920 HDMI\WFC Files\slm6374_at785_WFC.bmp'
        WFC = cv2.imread(WFC_path)
        for num in range(256):
            for i in range(1200):
                for j in range(1920):
                    if (j // 8)% 2 ==1:
                        # background[i,j] = int(255*(j%128+1)/128) # Gradient
                        background[i,j] = num
            lens_phase_mask = lens_mask(4000,200)
            lens_phase_mask = lens_phase_mask.astype('uint8')

            overall_pm = ((background)%256).astype(np.uint8)
            path = rf'D:\Academic Files\Project 23-24\SLM Calibration\Stripes\stripes_{num}.bmp'
##            path_1 = rf'C:\Users\CaFMOT\Desktop\stripes_{num}.bmp'
            cv2.imwrite(path,overall_pm)
            print(f'Image{num} saved') 
    except Exception as error:
        print(error)
        traceback.print_exc()
        
def main():
    app = QApplication(sys.argv)
    font = QFont('Arial',10)
    app.setFont(font)
    dialog = PMUI()
    dialog.show()
    sys.exit(app.exec_())
        
##circ_pattern(200,10,20,20)
##lens_mask(4000,400)
##pmG_circ(400,12,1,180,20,0.2,4000,100)
##rec_pattern(4,4,100,1,20)
##Imperial_logo(1,180,4000,100)
##beam(1,600)
if __name__ == '__main__':
    main()

##array = np.zeros((1200,1920))
##cv2.imwrite(r'C:\Users\Zechidilin\Desktop\blank.bmp',array)
