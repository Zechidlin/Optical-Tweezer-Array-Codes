#
# **************************************************************************
#
# simple_rep_sequence.py                                   (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog replay cards. 
# Shows a simple sequence mode example using only the few necessary commands
#


from pyspcm import *
from spcm_tools import *
import sys
import math 
from enum import IntEnum
import numpy as np
import pyspcm
import ctypes
import msvcrt
import time
import keyboard

if __name__ == "__main__":
    USING_EXTERNAL_TRIGGER = False
    LAST_STEP_OFFSET = 0

global lCardType
#
#**************************************************************************
# vWriteSegmentData: transfers the data for a segment to the card's memory
#**************************************************************************
#

def vWriteSegmentData (hCard, lNumActiveChannels, dwSegmentIndex, dwSegmentLenSample, pvSegData):
    lBytesPerSample = 2
    dwSegLenByte = uint32(dwSegmentLenSample * lBytesPerSample * lNumActiveChannels.value)

    # setup
    dwError = spcm_dwSetParam_i32(hCard, SPC_SEQMODE_WRITESEGMENT, dwSegmentIndex)
    if dwError == ERR_OK:
        dwError = spcm_dwSetParam_i32(hCard, SPC_SEQMODE_SEGMENTSIZE,  dwSegmentLenSample)

    # write data to board (main) sample memory
    if dwError == ERR_OK:
        dwError = spcm_dwDefTransfer_i64(hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, 0, pvSegData, 0, dwSegLenByte)
    if dwError == ERR_OK:
        dwError = spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)


#
# **************************************************************************
# DoDataCalculation: calculates and writes the output data for all segments
# **************************************************************************
#

# (main) sample memory segment index:
class SEGMENT_IDX(IntEnum):

    SEG_Q1SIN    =  0  # 4 first quadrant of sine signal
    SEG_Q2SIN    =  1  # 5 second quadrant of sine signal
    SEG_Q3SIN    =  2  # 6 third quadrant of sine signal
    SEG_Q4SIN    =  3  # 7 fourth quadrant of sine signal
    SEG_Q5SIN    =  4  # Last batch of double peak
    SEG_Q6SIN    =  5
    SEG_Q7SIN    =  6
    SEG_CHIRP21  =  7  # Chirp signal 2-->1
    SEG_CHIRP31  =  8  # Chirp signal 3-->1
    SEG_CHIRP323  =  9
    SEG_CHIRP12  =  10
    SEG_CHIRP322 = 11
    SEG_CSIN = 12
    SEG_LSIN = 13
    SEG_RSIN = 14
    SEG_C3SIN = 15
    
    
    
##    SEG_STOP     =  8  # DC level for stop/end


def vDoDataCalculation(lCardType, lNumActiveChannels, lMaxDACValue,hCard,beginvalue):

# Compute the waveform data for the card, then transfer data to the card
    
    global firstrun,resolution
    dwSegmentLenSample = uint32(0)
    dwSegLenByte       = uint32(0)


    resolution = 0.5
    nperiods = beginvalue / resolution
    sinfactor = int(nperiods * 2)

    distance = [0,60,-60]


    dwFactor = 1
    # This series has a slightly increased minimum size value.
    if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M5IEXPSERIES):
        dwFactor = 10

    # buffer for data transfer
    dwSegLenByte = 20000 * dwFactor * 512 * lNumActiveChannels.value  # max value taken from sine calculation below
    pvBuffer = pvAllocMemPageAligned(dwSegLenByte)
    pnData = cast(addressof(pvBuffer), ptr16)

    # helper values: Full Scale
    dwFS = uint32(lMaxDACValue.value)
    dwFShalf = uint32(dwFS.value // 2)
    amp = uint32(int(dwFShalf.value // 8))

            

    # Single tweezers

    # Central tweezer (2)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CSIN, dwSegmentLenSample, pvBuffer)

    # Left tweezer (1)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_LSIN, dwSegmentLenSample, pvBuffer)

    # Right tweezer (3)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[1])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_RSIN, dwSegmentLenSample, pvBuffer)
 
    

    #1 Three tweezers
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[1])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q1SIN, dwSegmentLenSample, pvBuffer)

    # Three tweezers, moved close to one another
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+20) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor-20) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_C3SIN, dwSegmentLenSample, pvBuffer)


    #2 Two tweezers (1,2)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q2SIN, dwSegmentLenSample, pvBuffer)

    #3 Two tweezers (1,3)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[1])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q3SIN, dwSegmentLenSample, pvBuffer)

    #4 Two tweezers (2,3)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[1])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q4SIN, dwSegmentLenSample, pvBuffer)


    #5 tweezer 1, and another tweezer moved close to it (can be either tweezer 2 or 3)
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor - 40) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q5SIN, dwSegmentLenSample, pvBuffer)

    #6 3 --> 2,and tweezer 2
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor + 20) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q6SIN, dwSegmentLenSample, pvBuffer)

    #7 1 --> 2,and tweezer 2
    dwSegmentLenSample = dwFactor * 128

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = (amp * np.sin((sinfactor - 20) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))+\
                 amp * np.sin((sinfactor+int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q7SIN, dwSegmentLenSample, pvBuffer)


    #8 Chirp signal 2 --> 1
    print("Transfering data, step 1/5")
    fchangerate = ((20000*sinfactor - 800000)/(20000*sinfactor+20000*int(distance[0]))-1)/(dwSegmentLenSample-1)
    dwSegmentLenSample = dwFactor * 128 * 20000 

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = ((amp * np.sin((20000*sinfactor+20000*int(distance[0])) * math.pi*(fchangerate*i+1)* i / (dwSegmentLenSample)))+\
                                               (amp * np.sin((20000*sinfactor+20000*int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CHIRP21, dwSegmentLenSample, pvBuffer)


    #9 Chirp signal 3 --> 1
    print("Transfering data, step 2/5")
    fchangerate = ((20000*sinfactor - 800000)/(20000*sinfactor+20000*int(distance[1]))-1)/(dwSegmentLenSample-1)
    dwSegmentLenSample = dwFactor * 128 * 20000  

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = ((amp * np.sin((20000*sinfactor+20000*int(distance[1])) * math.pi*(fchangerate*i+1)* i / (dwSegmentLenSample)))+\
                                                (amp * np.sin((20000*sinfactor+20000*int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CHIRP31, dwSegmentLenSample, pvBuffer)


    #10 Chirp signal 3 --> 2, 3 tweezers case
    print("Transfering data, step 3/5")
    fchangerate = ((20000*sinfactor + 400000)/(20000*sinfactor+20000*int(distance[1]))-1)/(dwSegmentLenSample-1)
    dwSegmentLenSample = dwFactor * 128 * 20000 

    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = ((amp * np.sin((20000*sinfactor+20000*int(distance[1])) * math.pi*(fchangerate*i+1)* i / (dwSegmentLenSample)))+\
                                                (amp * np.sin((20000*sinfactor+20000*int(distance[2])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))+\
                                                (amp * np.sin((20000*sinfactor+20000*int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CHIRP323, dwSegmentLenSample, pvBuffer)

    

    #11 Chirp signal 1 --> 2, 3 tweezers case
    print("Transfering data, step 4/5")
    fchangerate = ((20000*sinfactor - 400000)/(20000*sinfactor+20000*int(distance[2]))-1)/(dwSegmentLenSample-1)
    dwSegmentLenSample = dwFactor * 128 * 20000


    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = ((amp * np.sin((20000*sinfactor+20000*int(distance[2])) * math.pi*(fchangerate*i+1)* i / (dwSegmentLenSample)))+\
                                                (amp * np.sin((20000*sinfactor+20000*int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))+\
                                                (amp * np.sin((20000*sinfactor + 400000) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CHIRP12, dwSegmentLenSample, pvBuffer)

    #12 Chirp signal 3 --> 2, 2 tweezers case
    print("Transfering data, step 5/5")
    fchangerate = ((20000*sinfactor + 400000)/(20000*sinfactor+20000*int(distance[1]))-1)/(dwSegmentLenSample-1)
    dwSegmentLenSample = dwFactor * 128 * 20000 


    i = np.arange(dwSegmentLenSample)
    pnData = np.frombuffer(pvBuffer,dtype=np.int16,count=dwSegmentLenSample)
    pnData[:] = ((amp * np.sin((20000*sinfactor+20000*int(distance[1])) * math.pi*(fchangerate*i+1)* i / (dwSegmentLenSample)))+\
                                                (amp * np.sin((20000*sinfactor+20000*int(distance[0])) * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 1)))).astype(int16)
    vWriteSegmentData(hCard, lNumActiveChannels, SEGMENT_IDX.SEG_CHIRP322, dwSegmentLenSample, pvBuffer)


    sys.stdout.write("Data has been transferred to board memory!\n")






#
#**************************************************************************
# vWriteStepEntry
#**************************************************************************
#

def vWriteStepEntry(hCard, dwStepIndex, dwStepNextIndex, dwSegmentIndex, dwLoops, dwFlags):
    qwSequenceEntry = uint64(0)

    # setup register value
    qwSequenceEntry = (dwFlags & ~SPCSEQ_LOOPMASK) | (dwLoops & SPCSEQ_LOOPMASK)
    qwSequenceEntry <<= 32
    qwSequenceEntry |= ((dwStepNextIndex << 16)& SPCSEQ_NEXTSTEPMASK) | (int(dwSegmentIndex) & SPCSEQ_SEGMENTMASK)

    dwError = spcm_dwSetParam_i64(hCard, SPC_SEQMODE_STEPMEM0 + dwStepIndex, int64(qwSequenceEntry))


def stop(event):
    if event.event_type == keyboard.KEY_DOWN and event.name == 's':
        spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
        print("Card stopped!")
        keyboard.unhook_all()
        spcm_vClose(hCard)

    

#
# **************************************************************************
# vConfigureSequence
# **************************************************************************
#

def vConfigureSequence(hCard):
    # sequence memory

                          #  +-- StepIndex
                          #  |   +-- StepNextIndex
                          #  |   |  +-- SegmentIndex
                          #  |   |  |                          +-- Loops
                          #  |   |  |                          |   +-- Flags: SPCSEQ_ENDLOOPONTRIG
 #   Example              #  |   |  |                          |   |          For using this flag disable Software-Trigger above.
 #  vWriteStepEntry (hCard,  0,  1, SEGMENT_IDX.SEG_Q1SIN,     9,  0)

   # Initial sequence: all three tweezers are on
    vWriteStepEntry (hCard,  0,  1, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard,  1,  2, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard,  2,  3, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard,  3,  4, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard,  4,  0, SEGMENT_IDX.SEG_Q1SIN,     1,  0)



    # Q3 --> tweezer 1, Q2 --> tweezer 3, Q1 --> tweezer 2
    # tweezer 1
    vWriteStepEntry (hCard,  8,   9, SEGMENT_IDX.SEG_LSIN,    1,  0)
    vWriteStepEntry (hCard,  9,  10, SEGMENT_IDX.SEG_LSIN,    1,  0)
    vWriteStepEntry (hCard,  10,  11, SEGMENT_IDX.SEG_LSIN,    1,  0)
    vWriteStepEntry (hCard,  11,  12, SEGMENT_IDX.SEG_LSIN,    1,  0)
    vWriteStepEntry (hCard,  12,  8, SEGMENT_IDX.SEG_LSIN,    1,  0)

    # tweezer 2
    vWriteStepEntry (hCard,  16,  17, SEGMENT_IDX.SEG_CSIN,    1,  0)
    vWriteStepEntry (hCard,  17,  18, SEGMENT_IDX.SEG_CSIN,    1,  0)
    vWriteStepEntry (hCard,  18,  19, SEGMENT_IDX.SEG_CSIN,    1,  0)
    vWriteStepEntry (hCard,  19,  20, SEGMENT_IDX.SEG_CSIN,    1,  0)
    vWriteStepEntry (hCard,  20,  16, SEGMENT_IDX.SEG_CSIN,    1,  0)

    # tweezer 3
    vWriteStepEntry (hCard,  24,  25, SEGMENT_IDX.SEG_RSIN,    1,  0)
    vWriteStepEntry (hCard,  25,  26, SEGMENT_IDX.SEG_RSIN,    1,  0)
    vWriteStepEntry (hCard,  26,  27, SEGMENT_IDX.SEG_RSIN,    1,  0)
    vWriteStepEntry (hCard,  27,  28, SEGMENT_IDX.SEG_RSIN,    1,  0)
    vWriteStepEntry (hCard,  28,  24, SEGMENT_IDX.SEG_RSIN,    1,  0)

    # Third three scenarios: 2 occupied tweezers

    # tweezers 1,2
    vWriteStepEntry (hCard,  32,  33,  SEGMENT_IDX.SEG_Q2SIN,    1,  0)
    vWriteStepEntry (hCard,  33,  34,  SEGMENT_IDX.SEG_Q2SIN,    1,  0)
    vWriteStepEntry (hCard,  34,  35,  SEGMENT_IDX.SEG_Q2SIN,    1,  0)
    vWriteStepEntry (hCard,  35,  36,  SEGMENT_IDX.SEG_Q2SIN,    1,  0)
    vWriteStepEntry (hCard,  36,  32,  SEGMENT_IDX.SEG_Q2SIN,    1,  0)
    
    # tweezers 1,3
    vWriteStepEntry (hCard,  40,  41,  SEGMENT_IDX.SEG_Q3SIN,    1,  0)
    vWriteStepEntry (hCard,  41,  42,  SEGMENT_IDX.SEG_Q3SIN,    1,  0)
    vWriteStepEntry (hCard,  42,  43,  SEGMENT_IDX.SEG_Q3SIN,    1,  0)
    vWriteStepEntry (hCard,  43,  44,  SEGMENT_IDX.SEG_Q3SIN,    1,  0)
    vWriteStepEntry (hCard,  44,  40,  SEGMENT_IDX.SEG_Q3SIN,    1,  0)
    
    # tweezers 2,3
    vWriteStepEntry (hCard,  48,  49,  SEGMENT_IDX.SEG_Q4SIN,    1,  0)
    vWriteStepEntry (hCard,  49,  50,  SEGMENT_IDX.SEG_Q4SIN,    1,  0)
    vWriteStepEntry (hCard,  50,  51,  SEGMENT_IDX.SEG_Q4SIN,    1,  0)
    vWriteStepEntry (hCard,  51,  52,  SEGMENT_IDX.SEG_Q4SIN,    1,  0)
    vWriteStepEntry (hCard,  52,  48,  SEGMENT_IDX.SEG_Q4SIN,    1,  0)

    # Move tweezer 2 close to tweezer 1
    vWriteStepEntry (hCard,  56,  57,  SEGMENT_IDX.SEG_CHIRP21,    1,  0)
    vWriteStepEntry (hCard,  57,  58,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  58,  59,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  59,  60,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  60,  57,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)

    # Move tweezer 3 close to tweezer 1
    vWriteStepEntry (hCard,  64,  65,  SEGMENT_IDX.SEG_CHIRP31,    1,  0)
    vWriteStepEntry (hCard,  65,  66,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  66,  67,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  67,  68,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)
    vWriteStepEntry (hCard,  68,  65,  SEGMENT_IDX.SEG_Q5SIN,    1,  0)

    # Move tweezer 3 close to tweezer 2
    vWriteStepEntry (hCard,  72,  73,  SEGMENT_IDX.SEG_CHIRP322,    1,  0)
    vWriteStepEntry (hCard,  73,  74,  SEGMENT_IDX.SEG_Q6SIN,    1,  0)
    vWriteStepEntry (hCard,  74,  75,  SEGMENT_IDX.SEG_Q6SIN,    1,  0)
    vWriteStepEntry (hCard,  75,  76,  SEGMENT_IDX.SEG_Q6SIN,    1,  0)
    vWriteStepEntry (hCard,  76,  73,  SEGMENT_IDX.SEG_Q6SIN,    1,  0)

    # Move tweezer 3 close to tweezer 2, then move tweezer 1 close to tweezer 2
    vWriteStepEntry (hCard,  80,  81,  SEGMENT_IDX.SEG_CHIRP323,  1,  0)
    vWriteStepEntry (hCard,  81,  82,  SEGMENT_IDX.SEG_CHIRP12,  1,  0)
    vWriteStepEntry (hCard,  82,  83,  SEGMENT_IDX.SEG_C3SIN,    1,  0)
    vWriteStepEntry (hCard,  83,  84,  SEGMENT_IDX.SEG_C3SIN,    1,  0)
    vWriteStepEntry (hCard,  84,  82,  SEGMENT_IDX.SEG_C3SIN,    1,  0)

    # Transition
    vWriteStepEntry (hCard,  88,  89, SEGMENT_IDX.SEG_Q1SIN,     9,  0)
    vWriteStepEntry (hCard,  89,  90, SEGMENT_IDX.SEG_Q2SIN,     9,  0)
    vWriteStepEntry (hCard,  90,  91, SEGMENT_IDX.SEG_Q3SIN,     3,  0)
    vWriteStepEntry (hCard,  91,  92, SEGMENT_IDX.SEG_Q3SIN,     3,  0)
    vWriteStepEntry (hCard,  92,  88, SEGMENT_IDX.SEG_Q3SIN,     3,  0)


        

    # all our sequences come in groups of three segments
    global LAST_STEP_OFFSET
    LAST_STEP_OFFSET = 4


    # Configure the beginning (index of first seq-entry to start) of the sequence replay.
    spcm_dwSetParam_i32(hCard, SPC_SEQMODE_STARTSTEP, 0)


#
# **************************************************************************
# main 
# **************************************************************************
#

# Run the card

def RunBoard():

# Restate the default configuration of steps,start the card, and turn off unoccupied tweezers
    
    global hCard,beginvalue,resolution,noccupiedtweezer,tweezer,USING_EXTERNAL_TRIGGER,dwSequenceActual,llStep,dwSequenceNext
    vConfigureSequence(hCard)
    spcm_dwSetParam_i32(hCard, SPC_SEQMODE_STARTSTEP, 0)
    # We'll start and wait until all sequences are replayed.
    dwErr = spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
    if dwErr != ERR_OK:
        spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
        sys.stdout.write("... Error: {0:d}\n".format(dwErr))
        exit(1)
    

    lCardStatus = int32(0)
    dwSequenceActual = uint32(0)
    dwSequenceNext = uint32(0)
    lSeqStatusOld = int32(0)

    while True:
        if __name__ == "__main__":
            noccupiedtweezer = int(input("Assume we have ___ occupied tweezers... (enter 0,1,2, or 3) "))
        if noccupiedtweezer == 0:
            spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
            print("No occupied tweezers. Have another try.")
            break
        elif noccupiedtweezer == 3:
            dwSequenceNext = uint32(88)
            tweezer = ["1","2","3"]
            validinput = True
        else:
            validinput = False
            while not validinput:
                if __name__ == '__main__':
                    tweezer = input("And they are (combination of 1,2,3; seperated by comma) ... ")
                    tweezer = [value.strip() for value in tweezer.split(',')]
                print(f"{tweezer} is on. No. OcpT: {noccupiedtweezer}")
                if noccupiedtweezer == 1 and tweezer == ["1"]:
                    dwSequenceNext = uint32(8)
                    validinput = True
                elif noccupiedtweezer == 1 and tweezer == ["2"]:
                    dwSequenceNext = uint32(16)
                    validinput = True
                elif noccupiedtweezer == 1 and tweezer == ["3"]:
                    dwSequenceNext = uint32(24)
                    validinput = True
                elif noccupiedtweezer == 2 and tweezer == ["1","2"]:
                    dwSequenceNext = uint32(32)
                    validinput = True
                elif noccupiedtweezer == 2 and tweezer == ["1","3"]:
                    dwSequenceNext = uint32(40)
                    validinput = True
                elif noccupiedtweezer == 2 and tweezer == ["2","3"]:
                    dwSequenceNext = uint32(48)
                    validinput = True
                elif noccupiedtweezer == 3 and tweezer == ["1","2","3"]:
                    validinput = True
                else:
                    print("Wrong input form. Start over")
        

        
        if USING_EXTERNAL_TRIGGER is False:
            startime = time.perf_counter()
##            dwSequenceNext = uint32(dwSequenceActual.value + stepindex)

            # switch to next sequence
            # (before it is possible to overwrite the segment data of the new used segments with new values)
            llStep = int64(0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref(llStep))
            llStep = int64((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)
            if dwErr != ERR_OK:
                spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
                sys.stdout.write("Step setup error: {0:d}\n".format(dwErr))

            dwSequenceActual = dwSequenceNext
            endtime = time.perf_counter()
            duration = (endtime - startime)*1e6
            print(f"Duration is {duration:.2f} microseconds")
            break

    currentstep = uint32(0)
    spcm_dwGetParam_i32(hCard,SPC_SEQMODE_STATUS,byref(currentstep))
    print(f"Unoccupied tweezers are off. Current step index: {dwSequenceActual.value}. Press D to move effective ones closer.")
            


def cardsetup():

# Settings before starting the card: channels to be used, trigger modes, sample rate
    
    global hCard,lCardType,lNumChannels,llChEnable,lMaxADCValue
    hCard = spcm_hOpen(create_string_buffer(b'/dev/spcm0'))
    print("Finding a card...")
    if hCard == None:
        sys.stdout.write("no card found...\n")
        exit(1)

    lCardType = int32(0)
    spcm_dwGetParam_i32(hCard, SPC_PCITYP, byref(lCardType))
    lSerialNumber = int32(0)
    spcm_dwGetParam_i32(hCard, SPC_PCISERIALNO, byref(lSerialNumber))
    lFncType = int32(0)
    spcm_dwGetParam_i32(hCard, SPC_FNCTYPE, byref(lFncType))
    lMemSize = int32(2048) #
    spcm_dwSetParam_i64(hCard,SPC_MEMSIZE,lMemSize) #

    sCardName = szTypeToName(lCardType.value)
    if lFncType.value == SPCM_TYPE_AO:
        sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName, lSerialNumber.value))
    elif lFncType.value != SPCM_TYPE_AO:
        print("Card type not supported or the card is being used by another program")


    # set up the mode
    llChEnable = int64(CHANNEL0)
    lMaxSegments = int32(16) # 32
    spcm_dwSetParam_i32(hCard, SPC_CARDMODE,            SPC_REP_STD_SEQUENCE)
    spcm_dwSetParam_i64(hCard, SPC_CHENABLE,            llChEnable)
    spcm_dwSetParam_i32(hCard, SPC_SEQMODE_MAXSEGMENTS, lMaxSegments)

    # set up trigger
    spcm_dwSetParam_i32(hCard, SPC_TRIG_ORMASK,      SPC_TMASK_SOFTWARE)  # software trigger
    spcm_dwSetParam_i32(hCard, SPC_TRIG_ANDMASK,     0)
    spcm_dwSetParam_i32(hCard, SPC_TRIG_CH_ORMASK0,  0)
    spcm_dwSetParam_i32(hCard, SPC_TRIG_CH_ORMASK1,  0)
    spcm_dwSetParam_i32(hCard, SPC_TRIG_CH_ANDMASK0, 0)
    spcm_dwSetParam_i32(hCard, SPC_TRIG_CH_ANDMASK1, 0)
    spcm_dwSetParam_i32(hCard, SPC_TRIGGEROUT,       0)

    # set up the channels
    lNumChannels = int32(0)
    spcm_dwGetParam_i32(hCard, SPC_CHCOUNT, byref(lNumChannels))
    for lChannel in range(0, lNumChannels.value, 1):
        spcm_dwSetParam_i32(hCard, SPC_ENABLEOUT0    + lChannel * (SPC_ENABLEOUT1    - SPC_ENABLEOUT0),    1)
        spcm_dwSetParam_i32(hCard, SPC_AMP0          + lChannel * (SPC_AMP1          - SPC_AMP0),          1000)
        spcm_dwSetParam_i32(hCard, SPC_CH0_STOPLEVEL + lChannel * (SPC_CH1_STOPLEVEL - SPC_CH0_STOPLEVEL), SPCM_STOPLVL_HOLDLAST)

    # set samplerate to 1 MHz (M2i) or 50 MHz, no clock output
    spcm_dwSetParam_i32(hCard, SPC_CLOCKMODE, SPC_CM_INTPLL)
    if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES):
        spcm_dwSetParam_i64(hCard, SPC_SAMPLERATE, MEGA(640))
    else:
        spcm_dwSetParam_i64(hCard, SPC_SAMPLERATE, MEGA(1))
    spcm_dwSetParam_i32(hCard, SPC_CLOCKOUT,   0)

    lMaxADCValue = int32(0)
    spcm_dwGetParam_i32(hCard, SPC_MIINST_MAXADCVALUE, byref(lMaxADCValue))

    global extd,exth
    extd = False
    exth = False
    print("Card has been setup")
    return True



def run(event,exth):

# Go back to step 0, and start over
    
    global firstrun,dwSequenceActual,llStep,tweezer,dwSequenceNext
    if __name__ == "__main__":
        if (event.event_type == keyboard.KEY_DOWN and event.name == 'space'):

            print(f"Tweezers at presence: {tweezer}.Current step: {dwSequenceActual.value}")
            dwSequenceNext = uint32(0)
            # switch to next sequence

            llStep = int64(0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref(llStep))
            llStep = int64((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)
            dwSequenceActual = dwSequenceNext
            print(f"Card reinitialized. Current step index:{dwSequenceActual.value}")
            spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
            RunBoard()
    else:
        if exth == True:
            print(f"Tweezers at presence: {tweezer}.Current step: {dwSequenceActual.value}")
            dwSequenceNext = uint32(0)
            # switch to next sequence

            llStep = int64(0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref(llStep))
            llStep = int64((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)
            dwSequenceActual = dwSequenceNext
            print(f"Card reinitialized. Current step index:{dwSequenceActual.value}")
            spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
            RunBoard()

def dist(event,extd):

# Move 'on' tweezers closer to one another
    
    global resolution,dwSequenceActual,tweezer,dwSequenceNext
    if __name__ == "__main__":
        if (event.event_type == keyboard.KEY_DOWN and event.name == 'd'):
            if tweezer == ["1","2"]:
                dwSequenceNext = uint32(56)
            elif tweezer == ["1","3"]:
                dwSequenceNext = uint32(64)
            elif tweezer == ["2","3"]:
                dwSequenceNext = uint32(72)
            elif tweezer == ["1","2","3"]:
                dwSequenceNext = uint32(80)
            print(f"Tweezers at presence: {tweezer}")

            # switch to next sequence
            llStep = int64(0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref(llStep))
            llStep = int64((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)
            if dwErr != ERR_OK:
                spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
                sys.stdout.write("Step setup error: {0:d}\n".format(dwErr))

            dwSequenceActual = dwSequenceNext
            print(f"Tweezers operated. Current step index:{dwSequenceActual.value}")
    else:
        if extd == True:
            if tweezer == ["1","2"]:
                dwSequenceNext = uint32(56)
            elif tweezer == ["1","3"]:
                dwSequenceNext = uint32(64)
            elif tweezer == ["2","3"]:
                dwSequenceNext = uint32(72)
            elif tweezer == ["1","2","3"]:
                dwSequenceNext = uint32(80)
            print(f"Tweezers at presence: {tweezer}")

            # switch to next sequence
            llStep = int64(0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref(llStep))
            llStep = int64((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64(hCard, int32(SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)
            if dwErr != ERR_OK:
                spcm_dwSetParam_i32(hCard, SPC_M2CMD, M2CMD_CARD_STOP)
                sys.stdout.write("Step setup error: {0:d}\n".format(dwErr))

            dwSequenceActual = dwSequenceNext
            print(f"Tweezers operated. Current step index:{dwSequenceActual.value}")
        





if __name__ == "__main__":
    print("The following values are all in MHz. Note that the resolution is set to be 0.5")
    beginvalue = int(input("Enter the central frequency required: "))
    cardsetup()
    vDoDataCalculation(lCardType, lNumChannels, int32(lMaxADCValue.value - 1),hCard,beginvalue)
    RunBoard()
##    keyboard.on_press(lambda event:dist(event,extd))
##    keyboard.on_press(lambda event:run(event,exth))
##    keyboard.on_press(stop)

    keyboard.wait()
    print("AWG card has been closed.")


    # clean up
    spcm_vClose(hCard)

