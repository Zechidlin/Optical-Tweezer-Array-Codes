import socket
import pickle
import numpy as np
from vimba import *
import ast
import traceback
import cv2
import os
import imageio
from ctypes import *
from scipy import misc
import ctypes

server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
server_socket.bind(('',12345))
server_socket.listen(1)

def frame_handler(cam,frame):
    shape = (480,640)
    buffer = frame.get_buffer()
    np_frame = np.frombuffer(buffer,dtype=np.uint8).reshape(shape)
    frame_data = pickle.dumps(np_frame)
    length = len(frame_data)
    client_socket.sendall(length.to_bytes(4,byteorder='big'))
    client_socket.sendall(frame_data)
    cam.queue_frame(frame)

    
awareness = ctypes.c_int()
errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)
cdll.LoadLibrary(r"C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\SDK\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper")
cdll.LoadLibrary(r"C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\SDK\ImageGen")
image_lib = CDLL("ImageGen")
SDK_created = False
print('C-enviornment constructed')
print('Waiting for commands...')

with Vimba.get_instance() as vimba:
    cams = vimba.get_all_cameras()
    with cams[0] as cam:                            
        while True:
            print('Ready for next operation')
            try:
                array_list = []
                client_socket,addr = server_socket.accept()
                print(f'Connected with {addr}')

                raw_command = client_socket.recv(2381000)
                if len(raw_command) <= 15:      
                    command = raw_command.decode().strip()
                    print(len(command))
                else:
                    command = raw_command
                if command[-2] == '0' or command[-2] == '1' or command[-2] == '2':
                    command = ast.literal_eval(command)
                    if int(list(command)[2])==0:
                        shape = (480,640)
                        cam.ExposureTime.set(int(list(command)[1]))
                        for frame in cam.get_frame_generator(limit=int(list(command)[0])):
                            buffer = frame.get_buffer()
                            np_frame = np.frombuffer(buffer,dtype=np.uint8).reshape(shape)
                            array_list.append(np_frame)

                        np_frame_array = np.array(array_list)
                        serialized_data = pickle.dumps(np_frame_array)
                        client_socket.sendall(serialized_data)
                        print('Image sent!')
                    elif int(list(command)[2])==1:
                        cam.ExposureTime.set(int(list(command)[1]))
                        cam.start_streaming(frame_handler,buffer_count=10)

                    elif int(list(command)[2])==2:
                        try:
                            cam.stop_streaming()
                            print('Streaming has ended')
                            feedback = 'y'
                            serialized_stop_feedback = pickle.dumps(feedback)
                            client_socket.sendall(serialized_stop_feedback)
                        except Exception as error:
                            feedback = 'n'
                            serialized_stop_feedback = pickle.dumps(feedback)
                            client_socket.sendall(serialized_stop_feedback)
                            pass
                    else:
                        print('Wrong input command!')


                else:
                    try:
                        print('Phase mask received')
                        actual_command = pickle.loads(raw_command)
                        serialized_data = actual_command[0]
                        phase_mask = serialized_data.reshape((1200,1920))
                        save_path = rf'C:\Users\cafmot\OneDrive - Imperial College London (2)\Desktop\Phase Masks\Current Phase Mask.bmp'
                        cv2.imwrite(save_path,phase_mask)
                        print('Phase mask saved')
                        if not SDK_created:
 
                            RGB = c_uint(1)
                            is_eight_bit_image = c_uint(0)

                            bCppOrPython = c_uint(1);
                            print('Creating SDK...')
                            slm_lib.Create_SDK(bCppOrPython);
                            print ("Blink SDK was successfully constructed");
                            SDK_created = True

                        height = c_uint(slm_lib.Get_Height());
                        width = c_uint(slm_lib.Get_Width());
                        depth = c_uint(slm_lib.Get_Depth());
                        center_x = c_uint(width.value//2);
                        center_y = c_uint(height.value//2);

                        success = slm_lib.Load_lut(r"C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\slm1234_at780_calibrated for setup_0520.lut");
                        if success > 0: 
                            print ("LoadLUT Successful")	
                        else:
                            print("LoadLUT Failed")


                        WFC_path = r'C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\WFC Files\slm6374_at785_WFC.bmp'
                        WFC = cv2.imread(WFC_path)
                        path_1 = rf'C:\Users\cafmot\OneDrive - Imperial College London (2)\Desktop\Phase Masks\Current Phase Mask.bmp'
                        gray_image = cv2.imread(path_1,cv2.IMREAD_GRAYSCALE)
                        red_image = np.zeros((gray_image.shape[0],gray_image.shape[1],3),dtype=np.uint8)
                        red_image[:,:,2] = gray_image
                        cv2.imwrite(rf'C:\Users\cafmot\OneDrive - Imperial College London (2)\Desktop\Phase Masks\red_scale_image.bmp',red_image)
                        Final_phase_mask = (red_image+WFC).astype(np.uint8)
                        Final_phase_mask = cv2.cvtColor(Final_phase_mask,cv2.COLOR_BGR2RGB)
                        save_path_final= rf'C:\Users\cafmot\OneDrive - Imperial College London (2)\Desktop\Phase Masks\Current Final Phase Mask.bmp'
                        cv2.imwrite(save_path_final,Final_phase_mask)
                        Final_phase_mask =Final_phase_mask.flatten()

                        slm_lib.Write_image(Final_phase_mask.ctypes.data_as(POINTER(c_ubyte)), is_eight_bit_image);
                        print('Phase mask has been loaded to SLM')
                        feedback = '1'
                        serialized_feedback = pickle.dumps(feedback)
                        client_socket.sendall(serialized_feedback)
                        
                    except Exception as error:
                        feedback = '0'
                        serialized_feedback = pickle.dumps(feedback)
                        client_socket.sendall(serialized_feedback)
                        pass
                    
                    

                    
            except Exception as error:
                print(f'{error}')
                traceback.print_exc()
                pass


        client_socket.close()
        print('Connection has been severed by this script')
    ##            break

server_socket.close()
