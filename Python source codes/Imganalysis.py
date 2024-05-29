from PyQt5.QtWidgets import QFrame,QCheckBox,QComboBox,QDialog,QApplication,QWidget,QLabel,QLineEdit,QPushButton,QVBoxLayout,QTextEdit,QHBoxLayout
from PyQt5.QtCore import QThread,pyqtSignal,pyqtSlot,Qt
from PyQt5.QtGui import QPixmap,QImage
from PIL import Image
import matplotlib.pyplot as plt
import statistics
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
import math
from scipy.optimize import curve_fit
import sys
import traceback

def spotsize(x,w0,x0):

    return 0.5*w0*(10**(-6))*np.sqrt(1+((0.01*(x-x0)**2)/((math.pi*((w0*(10**(-6)))**2)/(780*(10**(-9))))**2)))*(10**6)

def gaussian(x,A,mean,std,B):

    return A*np.exp(-((x-mean)**2)/(2*std**2))+B

def greyintensity(imagepath):
    
    image = Image.open(imagepath)

    if image.mode != 'I;16':
        image = image.convert('I')


    pixeldata = list(image.getdata())

    width, height = image.size

    intensitymatrix = np.reshape(pixeldata, (height, width))

    return intensitymatrix, pixeldata

def save(mat,path):

    np.savetxt(path,mat,fmt = '%.6f', delimiter = '\t')


def plot3D(intensitymatrix):

    height, width = intensitymatrix.shape

    x,y = np.meshgrid(range(width),range(height))

    fig = plt.figure(figsize=(19.2,14.4))

    ax = fig.add_subplot(111, projection='3d')

##    ax.set_xticks(np.arange(0,641,20))

    ax.set_xlabel('X')

    ax.set_ylabel('Y')

    ax.set_zlabel('Grey Intensity')

    surf = ax.plot_surface(x,y,intensitymatrix,cmap='coolwarm')

    cbar = fig.colorbar(surf,shrink=0.5,aspect=5)

    cbar.set_label('Intensity',fontsize=12,labelpad=15)

    plt.show()


def waist_measure(imagesize,root,name,image_format,guess_mean,guess_amp):

    result = greyintensity(rf"{root}\{name}{image_format}")

    greyintensitymatrix = result[0]

    y_intensity_profile = []

    for i in range(imagesize):
        averaged_intensity = 0
        for j in range(imagesize):
            averaged_intensity += greyintensitymatrix[i,j]
        averaged_intensity = averaged_intensity/imagesize # y-direction Gaussian

        y_intensity_profile.append(averaged_intensity)


    x_intensity_profile = []

    for i in range(imagesize):
        averaged_intensity = 0
        for j in range(imagesize):
            averaged_intensity += greyintensitymatrix[j,i]
        averaged_intensity = averaged_intensity/imagesize # x-direction Gaussian

        x_intensity_profile.append(averaged_intensity)


    x_max = max(x_intensity_profile)
    y_max = max(y_intensity_profile)

    print(f'A_x is {x_max}')
    print(f'A_y is {y_max}')

    x_threshold = x_max/(math.e**2)
    y_threshold = y_max/(math.e**2)

    print(f'Maximum values used are {x_max},{y_max}')

    # print(f'Threshold along x: {x_threshold}, along y: {y_threshold}')

    x = list(np.linspace(0,imagesize-1,imagesize))

    indices_x = [i for i,x in enumerate(x_intensity_profile) if x>x_threshold]
    indices_y = [i for i,x in enumerate(y_intensity_profile) if x>y_threshold]

    x_width = max(indices_x)-min(indices_x)
    y_width = max(indices_y)-min(indices_y)
    diameter = ((x_width+y_width)*5)
    waist = diameter # Diameter?
    
   # print(f'The averaged waist size is {(x_width+y_width)*5} um')

    x_width = (x_width*10)
    y_width = (y_width*10)

    initial_guess_y = [guess_amp,guess_mean,5,0]
    initial_guess_x = [guess_amp,guess_mean,5,0]

    poptx,pcovx = curve_fit(gaussian,x,x_intensity_profile,p0=initial_guess_x)
    popty,pcovy = curve_fit(gaussian,x,y_intensity_profile,p0=initial_guess_y)
    x_fit = gaussian(x,*poptx)
    print(poptx)
    y_fit = gaussian(x,*popty)

    plt.plot(x,x_intensity_profile,color='g',label='Intensity Profile Along x-direction')
    plt.plot(x,x_fit,color='r',label='Gaussian Fit for x-direction')
    plt.plot(x,y_intensity_profile,color='yellow',label='Intensity Profile Along y-direction')
    plt.plot(x,y_fit,color='b',label='Gaussian Fit for y-direction')

    plt.xlabel('Pixel Distance')
    plt.ylabel('Intensity')
    plt.title('Averaged Intensity Along x- And y- Directions')
    plt.legend()
    plt.savefig(r'C:\Users\Zechidilin\Desktop\MOTImages\waist_analysis.svg',dpi=100)
    plt.clf()

    return waist,x_width,y_width


def intensityanalysis(file_root,name,image_format):

    result = greyintensity(rf"{file_root}\{name}{image_format}")

    greyintensitymatrix = result[0]
    
    pixeldata = result[1]

    MeanIntensity = sum(pixeldata)/len(pixeldata)

    MinIntensity = min(pixeldata)

    MaxIntensity = max(pixeldata)

    Std = statistics.stdev(pixeldata)

    return MeanIntensity,MinIntensity,MaxIntensity,Std

def lens(init_distance,final_distance,stepsize,name,root,imagesize,image_format):

    ## Root: location of the folder in which photos are

    x_width_list = []
    y_width_list = []
    waist = []

    num_photos = int(((final_distance-init_distance)/stepsize)+1)

    for index in range(num_photos):

        indvname = name+str(float(init_distance+index*stepsize))+'cm_1'

        # file_root = rf'{root}\{name}{init_distance+index*stepsize}cm_1'

        wresult = waist_measure(imagesize,root,indvname,image_format)

        waist_indv = wresult[0]

        x_width_indv = wresult[1]

        y_width_indv = wresult[2]

        x_width_list.append(x_width_indv)

        y_width_list.append(y_width_indv)

        waist.append(waist_indv)

    distance = np.linspace(init_distance,final_distance,num_photos)

    np_waist = np.array(waist)
    np_xlist = np.array(x_width_list)
    np_ylist = np.array(y_width_list)

##    popt_x,pcov_x = curve_fit(spotsize,distance,np_xlist,p0=[800,-10])
##    popt_y,pcov_y = curve_fit(spotsize,distance,np_ylist,p0=[800,-10])

##    w0_x, x0_x = popt_x
##    w0_y,x0_y = popt_y

    popt,pcov = curve_fit(spotsize,distance,np_waist,p0=[375,-40])
##    xwidth_fit = spotsize(distance,*popt_x)
##    ywidth_fit = spotsize(distance,*popt_y)
    spot_fit = spotsize(distance,*popt)

    plt.plot(distance,x_width_list,color='green',label='Width along x-direction / um')
    plt.plot(distance,y_width_list,color='yellow',label='Width along y-direction / um')
    plt.plot(distance,waist,color='black',label='Width averaged / um')
##    plt.plot(distance,xwidth_fit,color='red',label='Fitted curve for x-width')
##    plt.plot(distance,ywidth_fit,color='blue',label='Fitted curve for y-width')
    plt.plot(distance,spot_fit,color='r',label='Fitted curve for spot size')
    plt.xlabel('Distance from lens / cm')
    plt.ylabel('Spot size / um')
    plt.legend()
    plt.savefig(rf'{root}\lens_analysis.png',dpi=100)

    distance_prime = list(np.linspace(-123,37,65))
    spot_fit_prime = spotsize(distance_prime,*popt)
    plt.plot(distance_prime,spot_fit_prime,color='r')
    plt.xlabel('Distance from lens / cm')
    plt.ylabel('Spot size / um')
    plt.legend()
    plt.savefig(rf'{root}\lens_analysis_prime.png',dpi=100)

    return popt

class ImagePopup(QDialog):

    def __init__(self):

        super().__init__()
        self.setWindowTitle('Analysis Result')
        layout = QVBoxLayout()
        self.setLayout(layout)
        image_label = QLabel(self)
        image_label.setPixmap(QPixmap(image_path))

        layout.addWidget(image_label)
        
class ImageUI(QDialog):
    
    def __init__(self):

        super().__init__()
        self.setWindowTitle('Image Analysis Tool')
        self.setGeometry(300,400,750,300)
        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        self.initImageUI()

    def initImageUI(self):

        general_layout = QHBoxLayout()

        text_layout = QVBoxLayout()

        self.text_panel = QTextEdit(self)
        self.text_panel.setReadOnly(True)

        self.clear_button = QPushButton('Clear')
        self.clear_button.clicked.connect(self.clear_text)

        text_layout.addWidget(self.text_panel)
        text_layout.addWidget(self.clear_button)
        

        control_layout = QVBoxLayout()

        file_selection_layout = QVBoxLayout()

        self.file_path_label = QLabel('Image Path')
        self.file_path_selection = QComboBox(self)
        self.file_path_selection.addItem(r'C:\Users\CaFMOT\Desktop\MOTImages')
        self.file_path_selection.addItem(r'C:\Users\CaFMOT\Desktop')
        self.file_path_selection.addItem(r'C:\Users\CaFMOT\Desktop\SLM Images')
        self.file_path_selection.addItem(r'C:\Users\CaFMOT\Desktop\SLM Images\2by2_G=0.1')
        self.file_path_selection.addItem(r'C:\Users\Zechidilin\Desktop')

        image_name_layout = QHBoxLayout()

        self.image_heading_label = QLabel('Image Name')
        self.image_heading_input = QLineEdit(self)
        self.image_heading_input.setText('incident_')

        self.image_format = QComboBox(self)
        self.image_format.addItem('.tif')
        self.image_format.addItem('.tiff')
        self.image_format.addItem('.png')
        self.image_format.addItem('.jpeg')
        self.image_format.addItem('.bmp')

        image_name_layout.addWidget(self.image_heading_label)
        image_name_layout.addWidget(self.image_heading_input)
        image_name_layout.addWidget(self.image_format)

        self.image_selection = QPushButton('Select Image Directory')

        file_selection_layout.addWidget(self.file_path_label)
        file_selection_layout.addWidget(self.file_path_selection)
        file_selection_layout.addLayout(image_name_layout)

        self.intensity_analysis_button = QPushButton('Intensity Analysis')
        self.intensity_analysis_button.clicked.connect(self.intensity_analysis)
        file_selection_layout.addWidget(self.intensity_analysis_button)
        

        operations_layout = QHBoxLayout()

        waist_layout = QVBoxLayout()
        img_size_layout = QHBoxLayout()
        
        self.waist = QLabel('Beam size Measurement')
        self.image_size_label = QLabel('Image Size / pixels')
        self.image_size_input = QLineEdit(self)
        self.image_size_input.setText('100')
        img_size_layout.addWidget(self.image_size_label)
        img_size_layout.addWidget(self.image_size_input)
        waist_layout.addWidget(self.waist)
        waist_layout.addLayout(img_size_layout)
        self.guess_mean_label = QLabel('Fit Guess - Mean')
        self.guess_mean_input = QLineEdit(self)
        self.guess_mean_input.setText('25')
        self.guess_amp_label = QLabel('Fit Guess - Amplitude')
        self.guess_amp_input = QLineEdit(self)
        self.guess_amp_input.setText('100')
        self.waist_measurement_button = QPushButton('Measure beam size')
        self.waist_measurement_button.clicked.connect(self.waist_measurement)

        
        self.iiiD_plot_button = QPushButton('3D Intensity Distribution')
        self.iiiD_plot_button.clicked.connect(self.iiiD_plot)
        file_selection_layout.addWidget(self.iiiD_plot_button)

        self.histogram_button = QPushButton('Intensity Histogram')
        self.histogram_button.clicked.connect(self.histogram)
        file_selection_layout.addWidget(self.histogram_button)

        
        waist_layout.addWidget(self.guess_mean_label)
        waist_layout.addWidget(self.guess_mean_input)
        waist_layout.addWidget(self.guess_amp_label)
        waist_layout.addWidget(self.guess_amp_input)
        waist_layout.addWidget(self.waist_measurement_button)

        operations_layout.addLayout(waist_layout)

        lens_layout = QVBoxLayout()
        init_distance_layout = QHBoxLayout()
        final_distance_layout = QHBoxLayout()
        step_size_layout = QHBoxLayout()

        self.lens_label = QLabel('Beam Characterisation')
        lens_layout.addWidget(self.lens_label)

        self.init_distance_label = QLabel('Initial Distance / cm')
        self.init_distance_input = QLineEdit(self)
        init_distance_layout.addWidget(self.init_distance_label)
        init_distance_layout.addWidget(self.init_distance_input)
        self.init_distance_input.setText('10')
        lens_layout.addLayout(init_distance_layout)

        self.final_distance_label = QLabel('Final Distance / cm')
        self.final_distance_input = QLineEdit(self)
        self.final_distance_input.setText('30')
        final_distance_layout.addWidget(self.final_distance_label)
        final_distance_layout.addWidget(self.final_distance_input)
        lens_layout.addLayout(final_distance_layout)

        self.stepsize_label = QLabel('Stepsize / cm')
        self.stepsize_input = QLineEdit(self)
        self.stepsize_input.setText('2.5')
        step_size_layout.addWidget(self.stepsize_label)
        step_size_layout.addWidget(self.stepsize_input)
        lens_layout.addLayout(step_size_layout)
        
        self.lens_button = QPushButton('Beam Behavior Analysis')
        self.lens_button.clicked.connect(self.lens_characterisation)
        lens_layout.addWidget(self.lens_button)

        operations_layout.addLayout(lens_layout)

        control_layout.addLayout(file_selection_layout)
        control_layout.addLayout(operations_layout)

        general_layout.addLayout(control_layout)
        general_layout.addLayout(text_layout)

        self.setLayout(general_layout)

    def clear_text(self):

        self.text_panel.clear()

    def intensity_analysis(self):
        try:
            file_root = self.file_path_selection.currentText()
            name = self.image_heading_input.text()
            image_format = self.image_format.currentText()
            self.intensity_thread = intensitythread(file_root,name,image_format)
            self.intensity_thread.intensitythread_end.connect(self.intensity_end)
            self.intensity_thread.start()
            self.text_panel.append('Intensity analysis performed')
        except Exception as error:
            print(error)
            self.text_panel.append(f'Intensity error: {error}')
            traceback.print_exec()

    def intensity_end(self,mean,minint,maxint,std):
        
        try:
            print('Signal emitted')
            self.text_panel.append(f'Mean Intensity value: {mean}')
            self.text_panel.append(f'Minimum Intensity value: {minint}')
            self.text_panel.append(f'Max Intensity value: {maxint}')
            self.text_panel.append(f'Stand Deviation: {std}')

        except Exception as error:
            self.text_panel.append(f'Intensity end error: {error}')
            traceback.print_exc()

    def waist_measurement(self):

        try:

            imagesize = self.image_size_input.text()
            file_root = self.file_path_selection.currentText()
            name = self.image_heading_input.text()
            image_format = self.image_format.currentText()
            guess_mean= self.guess_mean_input.text()
            guess_amp = self.guess_amp_input.text()
            self.waist_thread = waistthread(imagesize,file_root,name,image_format,guess_mean,guess_amp)
            self.waist_thread.waist_end.connect(self.waist_outcome)
            self.waist_thread.start()
        

        except Exception as error:

            self.text_panel.append(f'Waist measurement error: {error}')
            traceback.print_exc()

    def waist_outcome(self,waist_result):

        self.text_panel.append(f'Measured beam diameter: {waist_result} um')
        self.text_panel.append('Analysis Plots have been saved to the current directory')


    def iiiD_plot(self):
        
        try:
            imagesize = self.image_size_input.text()
            file_root = self.file_path_selection.currentText()
            name = self.image_heading_input.text()
            image_format = self.image_format.currentText()
##            self.iiiD_plot_thread = iiiDthread(imagesize,file_root,name,image_format)
##            self.iiiD_plot_thread.start()
            image_path = rf'{file_root}\{name}{image_format}'
            intensitymatrix_iiiD = greyintensity(image_path)[0]
            plot3D(intensitymatrix_iiiD)
            
        except Exception as error:
            self.text_panel.append(f'3D plot error: {error}')
            traceback.print_exc()

    def histogram(self):
        try:
            file_root = self.file_path_selection.currentText()
            name = self.image_heading_input.text()
            image_format = self.image_format.currentText()
            image_path = rf'{file_root}\{name}{image_format}'
            intensitymatrix = greyintensity(image_path)[0].flatten()
            intensitymatrix = intensitymatrix[intensitymatrix<10]

            plt.hist(intensitymatrix,bins=30,alpha=0.5,color='blue',edgecolor='black')
            plt.title('Intensity Histogram')
            plt.xlabel('Value')
            plt.ylabel('Frequency')

            plt.show()
        except Exception as error:
            self.text_panel.append(f'3D plot error: {error}')
            traceback.print_exc()
   

    def lens_characterisation(self):

        try:

            initdistance = float(self.init_distance_input.text())
            finaldistance = float(self.final_distance_input.text())
            image_format = self.image_format.currentText()
            stepsize = float(self.stepsize_input.text())
            name = self.image_heading_input.text()
            root = self.file_path_selection.currentText()
            imagesize = int(self.image_size_input.text())
            self.lens_thread = lensthread(initdistance,finaldistance,stepsize,name,root,imagesize,image_format)
            self.lens_thread.lens_end.connect(self.lens_outcome)
            self.lens_thread.start()

        except Exception as error:

            self.text_panel.append(f'Lens characterisation error: {error}')
            traceback.print_exc()

    def lens_outcome(self,w0,x0):
        self.text_panel.append(f'Fitted waist size: {0.25*w0} um')
        self.text_panel.append(f'Fitted waist position: {x0} cm')
        self.text_panel.append('Analysis plot has been saved to selected directory')


            
            
        
class intensitythread(QThread):
    intensitythread_end = pyqtSignal(float,int,int,float)

    def __init__(self,file_root,name,image_format):

        super().__init__()
        self.file_root = file_root
        self.name = name
        self.image_format = image_format
        

    def run(self):
    
        try:
            Intresult = intensityanalysis(self.file_root,self.name,self.image_format)
            mean = Intresult[0]
            minint = Intresult[1]
            maxint = Intresult[2]
            std = Intresult[3]
            self.intensitythread_end.emit(mean,minint,maxint,std)
            
        except Exception as error:
            print(f'Intensity thread error: {error}')
            
        traceback.print_exc()

class waistthread(QThread):
    waist_end = pyqtSignal(int)

    def __init__(self,imagesize,file_root,name,image_format,guess_mean,guess_amp):

        super().__init__()
        self.imagesize = int(imagesize)
        self.file_root = file_root
        self.name = name
        self.image_format = image_format
        self.guess_mean = int(guess_mean)
        self.guess_amp = int(guess_amp)

    def run(self):

        try:

            waist_result = waist_measure(self.imagesize,self.file_root,self.name,self.image_format,self.guess_mean,self.guess_amp)[0]
            self.waist_end.emit(waist_result)

        except Exception as error:

            print(f'Waist thread error: {error}')
            traceback.print_exc()

class lensthread(QThread):
    lens_end = pyqtSignal(float,float)

    def __init__(self,initdistance,finaldistance,stepsize,name,root,imagesize,image_format):

        super().__init__()
        self.initdistance = initdistance
        self.finaldistance =  finaldistance
        self.stepsize = stepsize
        self.name = name
        self.root = root
        self.imagesize = imagesize
        self.image_format = image_format
    
    def run(self):

        try:

            lens_result=lens(self.initdistance,self.finaldistance,self.stepsize,self.name,self.root,self.imagesize,self.image_format)
            w0 = lens_result[0]
            x0 = lens_result[1]
            self.lens_end.emit(w0,x0)

        except Exception as error:

            print(f'Lens thread error: {error}')
            traceback.print_exc()
            
    
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        dialog = ImageUI()
        dialog.show()
        sys.exit(app.exec_())
    except Exception as error:
        print(error)
        traceback.print_exc()




    
