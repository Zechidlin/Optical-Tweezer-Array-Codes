# Optical-Tweezer-Array-Codes
Basic control programs for the project on generating optical tweezer arrays. 

This repository contains 5 files:

1. Phase Mask.py. A control program with PyQt5-generated UI for the control of a Meadowlark Optics 1920*1200 8-bit SLM, including hologram generation, calibration data acquisition (in the format of a .csv file), and intensity equalisation. It also enables the control over an Allied Vision Marlin F033B camera.
2. GeneralUI_DDS.py. A control program for the Spectrum Instrumentation M4x-6631-x4 arbitrary waveform generator (AWG). It enables the multitone signal generation, amplitude/frequency ramping, and a mock experiment sequence for testing the tweezer status identification function. Note that it is only compatible with Spectrum Instrumentation cards with DDS firmware upgrade, and cannot work without pyspcm & py_headers. Similar to Phase Mask.py, it also enables the control over the same model of camera.
3. server_script. A server script run on another computer, which has the camera connected, for receiving commands from either Phase Mask.py or GeneralUI_DDS.py.
4. sequence_replay_tweezer. An old control program for the Spectrum Instrumentation AWG card, using sequence replay mode. Could generate a signal with 3 tones, simulating the control over three optical tweezers, including tweezer generation, turning off, and moving around.
5. Imganalysis.py. A simple image analysis tool developed for obtaining the waist sizes of Gaussian beams, or analysing the intensity features of greyscale images.

You are more than welcome to use these scripts and improve them. 
